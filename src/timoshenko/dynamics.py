"""Linear time-history response for restrained structural models.

The solver uses Newmark's average-acceleration method and classical Rayleigh
damping. It is a linear elastic response calculation; nonlinear material
behavior and time-varying support constraints are outside its scope.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Sequence, cast

import numpy as np

from .structural import StructuralModel, _assemble_released_system, _constraint_arrays
from .structural_3d import StructuralModel3D, assemble_matrices_3d


@dataclass(frozen=True)
class TimeHistoryResult:
    """Nodal response histories and support reaction histories."""

    time_s: tuple[float, ...]
    displacements: tuple[tuple[tuple[float, ...], ...], ...]
    velocities: tuple[tuple[tuple[float, ...], ...], ...]
    accelerations: tuple[tuple[tuple[float, ...], ...], ...]
    reactions: tuple[tuple[tuple[float, ...], ...], ...]
    free_dof_residual_norms: tuple[float, ...]
    method: str = "newmark_average_acceleration"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def analyze_time_history(
    model: StructuralModel | StructuralModel3D,
    time_s: Sequence[float] | np.ndarray,
    *,
    force_history_n: Sequence[Sequence[float]] | np.ndarray | None = None,
    base_acceleration_m_s2: Sequence[float] | np.ndarray | None = None,
    direction: str = "y",
    rayleigh_mass_per_s: float = 0.0,
    rayleigh_stiffness_s: float = 0.0,
    initial_displacements_m: Sequence[float] | np.ndarray | None = None,
    initial_velocities_m_s: Sequence[float] | np.ndarray | None = None,
) -> TimeHistoryResult:
    """Integrate a linear 2D or 3D model under forces and/or base acceleration.

    ``force_history_n`` has one row per time and one column per model degree of
    freedom (3 per node for 2D, 6 for 3D). Base acceleration is a scalar record
    in the selected global translational direction and is converted to
    equivalent inertia loads using the assembled mass matrix. The time vector
    must be uniformly spaced. Damping is ``alpha*M + beta*K``. The method is
    unconditionally stable for the linear system, but accuracy still depends
    on the selected time step. Initial accelerations at zero-mass coordinates
    are reported as zero; subsequent values follow the integrated displacement.
    """
    is_3d = isinstance(model, StructuralModel3D)
    if not is_3d and not isinstance(model, StructuralModel):
        raise TypeError("model must be a StructuralModel or StructuralModel3D")
    times = np.asarray(time_s, dtype=float)
    if times.ndim != 1 or times.size < 2 or not np.all(np.isfinite(times)):
        raise ValueError("time_s must contain at least two finite values")
    intervals = np.diff(times)
    dt = float(intervals[0])
    if dt <= 0.0 or not np.allclose(intervals, dt, rtol=1e-8, atol=1e-12):
        raise ValueError("time_s must be strictly increasing and uniformly spaced")
    alpha = float(rayleigh_mass_per_s)
    beta = float(rayleigh_stiffness_s)
    if not math.isfinite(alpha) or alpha < 0.0:
        raise ValueError("rayleigh_mass_per_s must be finite and non-negative")
    if not math.isfinite(beta) or beta < 0.0:
        raise ValueError("rayleigh_stiffness_s must be finite and non-negative")

    dofs_per_node = 6 if is_3d else 3
    dof_count = dofs_per_node * len(model.nodes)
    if force_history_n is None:
        loads = np.zeros((times.size, dof_count), dtype=float)
    else:
        loads = np.asarray(force_history_n, dtype=float)
        if loads.shape != (times.size, dof_count) or not np.all(np.isfinite(loads)):
            raise ValueError(
                f"force_history_n must be finite with shape ({times.size}, {dof_count})"
            )
        loads = loads.copy()

    if is_3d:
        model_3d = cast(StructuralModel3D, model)
        stiffness, mass = assemble_matrices_3d(model_3d)
        released_count = 0
    else:
        model_2d = cast(StructuralModel, model)
        stiffness, mass_value, _, _, _ = _assemble_released_system(model_2d, include_mass=True)
        assert mass_value is not None
        mass = mass_value
        for node_index, lumped_mass in enumerate(model_2d.nodal_lumped_masses_kg):
            mass[3 * node_index, 3 * node_index] += lumped_mass
            mass[3 * node_index + 1, 3 * node_index + 1] += lumped_mass
        released_count = stiffness.shape[0] - dof_count
    if released_count:
        # Public input and output are joint histories. Internal released-end
        # rotations have neither external force nor support acceleration.
        loads = np.pad(loads, ((0, 0), (0, released_count)))
    if base_acceleration_m_s2 is not None:
        valid_directions = {"x", "y", "z"} if is_3d else {"x", "y"}
        if direction not in valid_directions:
            raise ValueError(f"direction must be one of {sorted(valid_directions)}")
        ground = np.asarray(base_acceleration_m_s2, dtype=float)
        if ground.shape != (times.size,) or not np.all(np.isfinite(ground)):
            raise ValueError("base_acceleration_m_s2 must have one finite value per time step")
        influence = np.zeros(stiffness.shape[0], dtype=float)
        component = {"x": 0, "y": 1, "z": 2}[direction]
        influence[component:dof_count:dofs_per_node] = 1.0
        loads += (-mass @ influence) * ground[:, None]
    elif direction not in ({"x", "y", "z"} if is_3d else {"x", "y"}):
        raise ValueError("direction must name a translational axis supported by the model")

    if is_3d:
        restrained = np.asarray(model_3d.restraints, dtype=bool).reshape(-1)
    else:
        restrained, prescribed = _constraint_arrays(model_2d)
        if np.any(np.abs(prescribed[restrained]) > 0.0):
            raise ValueError("time-history analysis requires zero prescribed support displacements")
        if released_count:
            restrained = np.concatenate((restrained, np.zeros(released_count, dtype=bool)))
    free = np.flatnonzero(~restrained)
    if not len(free):
        raise ValueError("time-history analysis requires at least one free degree of freedom")
    kff = stiffness[np.ix_(free, free)]
    mff = mass[np.ix_(free, free)]
    cff = alpha * mff + beta * kff
    p = loads[:, free]

    n_free = len(free)
    u = np.zeros((times.size, n_free), dtype=float)
    v = np.zeros_like(u)
    a = np.zeros_like(u)
    if initial_displacements_m is not None:
        initial_u = np.asarray(initial_displacements_m, dtype=float)
        if initial_u.shape != (dof_count,) or not np.all(np.isfinite(initial_u)):
            raise ValueError(f"initial_displacements_m must have shape ({dof_count},)")
        u[0] = np.pad(initial_u, (0, released_count))[free]
    if initial_velocities_m_s is not None:
        initial_v = np.asarray(initial_velocities_m_s, dtype=float)
        if initial_v.shape != (dof_count,) or not np.all(np.isfinite(initial_v)):
            raise ValueError(f"initial_velocities_m_s must have shape ({dof_count},)")
        v[0] = np.pad(initial_v, (0, released_count))[free]
    try:
        initial_rhs = p[0] - cff @ v[0] - kff @ u[0]
        massful = np.flatnonzero(np.diag(mff) > 0.0)
        if len(massful) != n_free:
            a[0, massful] = np.linalg.solve(mff[np.ix_(massful, massful)], initial_rhs[massful])
        else:
            a[0] = np.linalg.solve(mff, initial_rhs)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "initial acceleration requires positive mass on every free degree of freedom"
        ) from exc

    gamma, newmark_beta = 0.5, 0.25
    effective = kff + (gamma / (newmark_beta * dt)) * cff + mff / (newmark_beta * dt**2)
    try:
        effective_inverse = np.linalg.inv(effective)
        for index in range(1, times.size):
            predictor_u = (
                u[index - 1] + dt * v[index - 1] + dt**2 * (0.5 - newmark_beta) * a[index - 1]
            )
            predictor_v = v[index - 1] + dt * (1.0 - gamma) * a[index - 1]
            effective_load = p[index] + mff @ (predictor_u / (newmark_beta * dt**2))
            effective_load += cff @ (gamma * predictor_u / (newmark_beta * dt) - predictor_v)
            u[index] = effective_inverse @ effective_load
            a[index] = (u[index] - predictor_u) / (newmark_beta * dt**2)
            v[index] = predictor_v + gamma * dt * a[index]
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "effective dynamic stiffness is singular; check restraints and model"
        ) from exc

    full_u = np.zeros((times.size, stiffness.shape[0]), dtype=float)
    full_v = np.zeros_like(full_u)
    full_a = np.zeros_like(full_u)
    full_u[:, free], full_v[:, free], full_a[:, free] = u, v, a
    residual = full_u @ stiffness.T + full_v @ (alpha * mass + beta * stiffness).T
    residual += full_a @ mass.T - loads
    residual_norms = tuple(float(np.linalg.norm(row[free])) for row in residual)
    reactions = residual[:, :dof_count].reshape((times.size, len(model.nodes), dofs_per_node))
    displacements = full_u[:, :dof_count].reshape((times.size, len(model.nodes), dofs_per_node))
    velocities = full_v[:, :dof_count].reshape((times.size, len(model.nodes), dofs_per_node))
    accelerations = full_a[:, :dof_count].reshape((times.size, len(model.nodes), dofs_per_node))

    def rows(values: np.ndarray) -> tuple[tuple[tuple[float, ...], ...], ...]:
        return tuple(tuple(tuple(float(v) for v in node) for node in frame) for frame in values)

    return TimeHistoryResult(
        time_s=tuple(float(value) for value in times),
        displacements=rows(displacements),
        velocities=rows(velocities),
        accelerations=rows(accelerations),
        reactions=rows(reactions),
        free_dof_residual_norms=residual_norms,
    )


__all__ = ["TimeHistoryResult", "analyze_time_history"]
