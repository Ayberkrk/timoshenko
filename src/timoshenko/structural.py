"""Small, explicit 2D elastic frame models and analysis routines.

The implementation uses a direct-stiffness frame formulation with three
degrees of freedom per node: global x translation, global y translation and
rotation about global z. Models use SI units throughout.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _positive(name: str, value: float) -> float:
    value = _finite(name, value)
    if value <= 0.0:
        raise ValueError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True)
class FrameNode:
    """A node in the global x-y plane, with coordinates in metres."""

    x_m: float
    y_m: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x_m", _finite("x_m", self.x_m))
        object.__setattr__(self, "y_m", _finite("y_m", self.y_m))


@dataclass(frozen=True)
class FrameMaterial:
    """Isotropic linear-elastic material properties used by a frame member."""

    youngs_modulus_pa: float
    shear_modulus_pa: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "youngs_modulus_pa", _positive("youngs_modulus_pa", self.youngs_modulus_pa))
        object.__setattr__(self, "shear_modulus_pa", _positive("shear_modulus_pa", self.shear_modulus_pa))


@dataclass(frozen=True)
class FrameSection:
    """Frame section data for a member in the x-y plane.

    ``second_moment_local_z_m4`` is the second moment for bending in the
    frame plane. ``shear_area_local_y_m2`` is an effective shear area. Leave
    it as ``None`` for Euler-Bernoulli bending; supply a verified effective
    area to use the Timoshenko shear-flexible stiffness.
    """

    area_m2: float
    second_moment_local_z_m4: float
    shear_area_local_y_m2: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "area_m2", _positive("area_m2", self.area_m2))
        object.__setattr__(
            self,
            "second_moment_local_z_m4",
            _positive("second_moment_local_z_m4", self.second_moment_local_z_m4),
        )
        if self.shear_area_local_y_m2 is not None:
            object.__setattr__(self, "shear_area_local_y_m2", _positive("shear_area_local_y_m2", self.shear_area_local_y_m2))


@dataclass(frozen=True)
class FrameMember:
    """A prismatic two-node frame member with optional local uniform loads.

    ``uniform_load_local_x_n_m`` and ``uniform_load_local_y_n_m`` are
    positive in the member's local axes. ``mass_per_length_kg_m`` is used by
    modal analysis and is not inferred from material or section data.
    """

    node_i: int
    node_j: int
    material: FrameMaterial
    section: FrameSection
    uniform_load_local_x_n_m: float = 0.0
    uniform_load_local_y_n_m: float = 0.0
    mass_per_length_kg_m: float | None = None

    def __post_init__(self) -> None:
        if isinstance(self.node_i, bool) or int(self.node_i) != self.node_i or self.node_i < 0:
            raise ValueError("node_i must be a non-negative integer")
        if isinstance(self.node_j, bool) or int(self.node_j) != self.node_j or self.node_j < 0:
            raise ValueError("node_j must be a non-negative integer")
        if self.node_i == self.node_j:
            raise ValueError("a frame member must connect two different nodes")
        if not isinstance(self.material, FrameMaterial) or not isinstance(self.section, FrameSection):
            raise TypeError("material and section must be FrameMaterial and FrameSection instances")
        object.__setattr__(self, "uniform_load_local_x_n_m", _finite("uniform_load_local_x_n_m", self.uniform_load_local_x_n_m))
        object.__setattr__(self, "uniform_load_local_y_n_m", _finite("uniform_load_local_y_n_m", self.uniform_load_local_y_n_m))
        if self.mass_per_length_kg_m is not None:
            value = _finite("mass_per_length_kg_m", self.mass_per_length_kg_m)
            if value < 0.0:
                raise ValueError("mass_per_length_kg_m must be non-negative")
            object.__setattr__(self, "mass_per_length_kg_m", value)


@dataclass(frozen=True)
class StructuralModel:
    """A linear 2D frame model with nodal loads and restrained degrees of freedom.

    Each restraint row is ``(fix_x, fix_y, fix_rotation)``. Each load row is
    ``(Fx_N, Fy_N, Mz_Nm)``. Nodal lumped masses contribute equally to the
    two translational degrees of freedom; member mass is supplied separately
    as mass per unit length.
    """

    nodes: Sequence[FrameNode]
    members: Sequence[FrameMember]
    restraints: Sequence[Sequence[bool]]
    nodal_loads: Sequence[Sequence[float]] = ()
    nodal_lumped_masses_kg: Sequence[float] = ()

    def __post_init__(self) -> None:
        nodes = tuple(self.nodes)
        members = tuple(self.members)
        if not nodes:
            raise ValueError("a structural model must contain at least one node")
        if any(not isinstance(node, FrameNode) for node in nodes):
            raise TypeError("nodes must contain FrameNode instances")
        if not members or any(not isinstance(member, FrameMember) for member in members):
            raise ValueError("members must contain at least one FrameMember")
        if any(max(member.node_i, member.node_j) >= len(nodes) for member in members):
            raise ValueError("member node indices must refer to nodes in the model")
        restraints = tuple(tuple(row) for row in self.restraints)
        if len(restraints) != len(nodes) or any(len(row) != 3 for row in restraints):
            raise ValueError("restraints must have one (fix_x, fix_y, fix_rotation) row per node")
        if any(not isinstance(value, (bool, np.bool_)) for row in restraints for value in row):
            raise TypeError("restraint values must be booleans")
        restraints = tuple(tuple(bool(value) for value in row) for row in restraints)
        if len(self.nodal_loads):
            loads = tuple(tuple(_finite("nodal load", value) for value in row) for row in self.nodal_loads)
            if len(loads) != len(nodes) or any(len(row) != 3 for row in loads):
                raise ValueError("nodal_loads must have one (Fx_N, Fy_N, Mz_Nm) row per node")
        else:
            loads = tuple((0.0, 0.0, 0.0) for _ in nodes)
        if len(self.nodal_lumped_masses_kg):
            masses = tuple(_finite("nodal_lumped_masses_kg", value) for value in self.nodal_lumped_masses_kg)
            if len(masses) != len(nodes) or any(value < 0.0 for value in masses):
                raise ValueError("nodal_lumped_masses_kg must contain one non-negative value per node")
        else:
            masses = tuple(0.0 for _ in nodes)
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "restraints", restraints)
        object.__setattr__(self, "nodal_loads", loads)
        object.__setattr__(self, "nodal_lumped_masses_kg", masses)


@dataclass(frozen=True)
class FrameAnalysisResult:
    """Frame displacements, reactions, member end actions and solver metadata."""

    displacements: tuple[tuple[float, float, float], ...]
    reactions: tuple[tuple[float, float, float], ...]
    member_end_forces_local: tuple[tuple[float, float, float, float, float, float], ...]
    strain_energy_j: float
    free_dof_residual_norm: float
    analysis_type: str = "first_order"
    iteration_count: int = 1


@dataclass(frozen=True)
class ModalAnalysisResult:
    """Natural frequencies and peak-normalized mode shapes of a frame model."""

    frequencies_hz: tuple[float, ...]
    mode_shapes: tuple[tuple[tuple[float, float, float], ...], ...]
    generalized_masses_kg: tuple[float, ...]
    constrained_dof_count: int
    notes: tuple[str, ...] = ()


def analyze_linear_static(model: StructuralModel) -> FrameAnalysisResult:
    """Solve one small-displacement, linear-elastic 2D frame load case.

    Element loads are uniform and expressed in local member coordinates.
    Supports are ideal restraints. The routine does not perform design-code
    checks, load combinations, geometric nonlinearity or 3D analysis.
    """
    if not isinstance(model, StructuralModel):
        raise TypeError("model must be a StructuralModel")
    stiffness, load, element_data = _assemble(model, include_member_loads=True)
    restrained = np.asarray(model.restraints, dtype=bool).reshape(-1)
    free = np.flatnonzero(~restrained)
    displacements = np.zeros(stiffness.shape[0], dtype=float)
    if len(free):
        try:
            displacements[free] = np.linalg.solve(stiffness[np.ix_(free, free)], load[free])
        except np.linalg.LinAlgError as exc:
            raise ValueError("the restrained frame stiffness is singular; check supports and member connectivity") from exc
    if not np.all(np.isfinite(displacements)):
        raise ValueError("frame solution produced non-finite displacements")
    residual = stiffness @ displacements - load
    residual_norm = float(np.linalg.norm(residual[free], ord=np.inf)) if len(free) else 0.0
    scale = max(1.0, float(np.linalg.norm(load, ord=np.inf)))
    if residual_norm > 1e-8 * scale:
        raise ValueError("frame solution did not satisfy free-degree equilibrium within tolerance")
    reactions = residual
    member_forces = []
    for member_index, member in enumerate(model.members):
        dofs, transform, local_stiffness, equivalent_load, _, _, _ = element_data[member_index]
        local_displacement = transform @ displacements[dofs]
        end_force = local_stiffness @ local_displacement - equivalent_load
        member_forces.append(tuple(float(value) for value in end_force))
    energy = 0.5 * float(displacements @ stiffness @ displacements)
    return FrameAnalysisResult(
        displacements=_node_rows(displacements),
        reactions=_node_rows(reactions),
        member_end_forces_local=tuple(member_forces),
        strain_energy_j=energy,
        free_dof_residual_norm=residual_norm,
    )


def analyze_p_delta(
    model: StructuralModel,
    *,
    maximum_iterations: int = 40,
    tolerance: float = 1e-8,
    relaxation: float = 0.7,
) -> FrameAnalysisResult:
    """Iterate a 2D frame tangent stiffness for approximate P-delta response.

    Axial member forces update an Euler-Bernoulli geometric stiffness while
    the material stiffness and member-load vector remain linear. The update
    uses member-average axial force and a relaxed fixed-point iteration. This
    is a small-displacement stability approximation, not a corotational or
    large-displacement analysis.
    """
    if not isinstance(model, StructuralModel):
        raise TypeError("model must be a StructuralModel")
    if isinstance(maximum_iterations, bool) or int(maximum_iterations) != maximum_iterations or maximum_iterations < 1:
        raise ValueError("maximum_iterations must be a positive integer")
    tolerance = _positive("tolerance", tolerance)
    relaxation = _finite("relaxation", relaxation)
    if not 0.0 < relaxation <= 1.0:
        raise ValueError("relaxation must be in (0, 1]")
    material_stiffness, load, element_data = _assemble(model, include_member_loads=True)
    restrained = np.asarray(model.restraints, dtype=bool).reshape(-1)
    free = np.flatnonzero(~restrained)
    if not len(free):
        displacement = np.zeros(material_stiffness.shape[0], dtype=float)
    else:
        try:
            displacement = np.zeros(material_stiffness.shape[0], dtype=float)
            displacement[free] = np.linalg.solve(material_stiffness[np.ix_(free, free)], load[free])
        except np.linalg.LinAlgError as exc:
            raise ValueError("the restrained frame stiffness is singular; check supports and member connectivity") from exc
    converged_iteration = 0
    tangent = material_stiffness
    for iteration in range(1, int(maximum_iterations) + 1):
        tangent, axial_forces = _p_delta_tangent(model, material_stiffness, element_data, displacement)
        trial = np.zeros_like(displacement)
        if len(free):
            eigenvalues = np.linalg.eigvalsh(tangent[np.ix_(free, free)])
            stiffness_scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
            if float(np.min(eigenvalues)) < -1e-12 * stiffness_scale:
                raise ValueError("P-delta tangent stiffness indicates frame instability")
            try:
                trial[free] = np.linalg.solve(tangent[np.ix_(free, free)], load[free])
            except np.linalg.LinAlgError as exc:
                raise ValueError("P-delta tangent stiffness is singular; the frame may have reached instability") from exc
        updated = displacement + relaxation * (trial - displacement)
        difference = float(np.linalg.norm(updated - displacement, ord=np.inf))
        reference = max(float(np.linalg.norm(updated, ord=np.inf)), 1e-12)
        displacement = updated
        if difference <= tolerance * reference:
            converged_iteration = iteration
            break
    if not converged_iteration:
        raise ValueError(f"P-delta iteration did not converge in {maximum_iterations} iterations")
    tangent, axial_forces = _p_delta_tangent(model, material_stiffness, element_data, displacement)
    residual = tangent @ displacement - load
    residual_norm = float(np.linalg.norm(residual[free], ord=np.inf)) if len(free) else 0.0
    scale = max(1.0, float(np.linalg.norm(load, ord=np.inf)))
    if residual_norm > max(1e-8, tolerance * 10.0) * scale:
        raise ValueError("P-delta solution did not satisfy free-degree equilibrium within tolerance")
    member_forces = []
    for data, axial_tension in zip(element_data, axial_forces):
        dofs, transform, local_stiffness, equivalent_load, length, _, _ = data
        local_displacement = transform @ displacement[dofs]
        end_force = local_stiffness @ local_displacement
        end_force += axial_tension * (_geometric_stiffness_unit(length) @ local_displacement)
        end_force -= equivalent_load
        member_forces.append(tuple(float(value) for value in end_force))
    strain_energy = 0.5 * float(displacement @ material_stiffness @ displacement)
    return FrameAnalysisResult(
        displacements=_node_rows(displacement),
        reactions=_node_rows(residual),
        member_end_forces_local=tuple(member_forces),
        strain_energy_j=strain_energy,
        free_dof_residual_norm=residual_norm,
        analysis_type="p_delta",
        iteration_count=converged_iteration,
    )


def analyze_modes(model: StructuralModel, *, mode_count: int = 6) -> ModalAnalysisResult:
    """Calculate undamped frame modes using a consistent translational mass matrix.

    Member mass uses an Euler-Bernoulli consistent mass matrix, even when
    static stiffness includes shear flexibility. Member rotary inertia and
    damping are not included. Restrained degrees of freedom are removed from
    the generalized eigenproblem.
    """
    if not isinstance(model, StructuralModel):
        raise TypeError("model must be a StructuralModel")
    if isinstance(mode_count, bool) or int(mode_count) != mode_count or mode_count < 1:
        raise ValueError("mode_count must be a positive integer")
    stiffness, _, element_data = _assemble(model, include_member_loads=False)
    mass = np.zeros_like(stiffness)
    for node_index, lumped_mass in enumerate(model.nodal_lumped_masses_kg):
        mass[3 * node_index, 3 * node_index] += lumped_mass
        mass[3 * node_index + 1, 3 * node_index + 1] += lumped_mass
    for member_index, member in enumerate(model.members):
        if member.mass_per_length_kg_m is None or member.mass_per_length_kg_m == 0.0:
            continue
        dofs, transform, _, _, length, _, _ = element_data[member_index]
        local_mass = _local_mass(member, length)
        mass[np.ix_(dofs, dofs)] += transform.T @ local_mass @ transform
    restrained = np.asarray(model.restraints, dtype=bool).reshape(-1)
    free = np.flatnonzero(~restrained)
    if not len(free):
        raise ValueError("modal analysis requires at least one unrestrained degree of freedom")
    kff, mff = stiffness[np.ix_(free, free)], mass[np.ix_(free, free)]
    try:
        lower = np.linalg.cholesky(mff)
    except np.linalg.LinAlgError as exc:
        raise ValueError("modal mass matrix is not positive definite; provide mass for every free component") from exc
    left_solved = np.linalg.solve(lower, kff)
    symmetric = np.linalg.solve(lower, left_solved.T).T
    symmetric = 0.5 * (symmetric + symmetric.T)
    eigenvalues, transformed_modes = np.linalg.eigh(symmetric)
    spectral_scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    negative_tolerance = 1e-10 * spectral_scale
    if float(np.min(eigenvalues)) < -negative_tolerance:
        raise ValueError("frame stiffness has a negative eigenvalue; the model is unstable")
    eigenvalues = np.where(eigenvalues < negative_tolerance, 0.0, eigenvalues)
    selected = np.argsort(eigenvalues)[: min(int(mode_count), len(eigenvalues))]
    frequencies, shapes, generalized_masses = [], [], []
    full_dof_count = stiffness.shape[0]
    for index in selected:
        vector_free = np.linalg.solve(lower.T, transformed_modes[:, index])
        generalized_mass = float(vector_free @ mff @ vector_free)
        if generalized_mass <= 0.0 or not math.isfinite(generalized_mass):
            raise ValueError("modal solution produced a non-positive generalized mass")
        vector_free /= math.sqrt(generalized_mass)
        vector = np.zeros(full_dof_count, dtype=float)
        vector[free] = vector_free
        translations = vector.reshape((-1, 3))[:, :2]
        peak = float(np.max(np.abs(translations)))
        if peak > 0.0:
            vector /= peak
            vector_free /= peak
        largest = int(np.argmax(np.abs(vector)))
        if vector[largest] < 0.0:
            vector *= -1.0
            vector_free *= -1.0
        frequencies.append(math.sqrt(float(eigenvalues[index])) / (2.0 * math.pi))
        shapes.append(_node_rows(vector))
        generalized_masses.append(float(vector_free @ mff @ vector_free))
    notes = ("Member rotary inertia and damping are omitted; member mass uses Euler-Bernoulli interpolation.",)
    return ModalAnalysisResult(
        frequencies_hz=tuple(frequencies),
        mode_shapes=tuple(shapes),
        generalized_masses_kg=tuple(generalized_masses),
        constrained_dof_count=int(np.count_nonzero(restrained)),
        notes=notes,
    )


def _assemble(model: StructuralModel, *, include_member_loads: bool):
    dof_count = 3 * len(model.nodes)
    stiffness = np.zeros((dof_count, dof_count), dtype=float)
    load = np.asarray(model.nodal_loads, dtype=float).reshape(-1)
    element_data = []
    for member in model.members:
        node_i, node_j = model.nodes[member.node_i], model.nodes[member.node_j]
        dx, dy = node_j.x_m - node_i.x_m, node_j.y_m - node_i.y_m
        length = math.hypot(dx, dy)
        if length <= np.finfo(float).eps * max(1.0, abs(node_i.x_m), abs(node_i.y_m), abs(node_j.x_m), abs(node_j.y_m)):
            raise ValueError("frame member length must be greater than zero at the model coordinate scale")
        cosine, sine = dx / length, dy / length
        local_stiffness = _local_stiffness(member, length)
        transform = _transformation(cosine, sine)
        dofs = np.asarray((3 * member.node_i, 3 * member.node_i + 1, 3 * member.node_i + 2,
                           3 * member.node_j, 3 * member.node_j + 1, 3 * member.node_j + 2), dtype=int)
        global_stiffness = transform.T @ local_stiffness @ transform
        stiffness[np.ix_(dofs, dofs)] += global_stiffness
        equivalent_load = _equivalent_local_load(member, length) if include_member_loads else np.zeros(6)
        if include_member_loads:
            load[dofs] += transform.T @ equivalent_load
        element_data.append((dofs, transform, local_stiffness, equivalent_load, length, cosine, sine))
    return stiffness, load, element_data


def _p_delta_tangent(model, material_stiffness, element_data, displacement):
    tangent = material_stiffness.copy()
    axial_forces = []
    for member, data in zip(model.members, element_data):
        dofs, transform, local_stiffness, equivalent_load, length, _, _ = data
        local_displacement = transform @ displacement[dofs]
        material_end_force = local_stiffness @ local_displacement - equivalent_load
        axial_tension = float((material_end_force[3] - material_end_force[0]) / 2.0)
        axial_forces.append(axial_tension)
        geometric = axial_tension * _geometric_stiffness_unit(length)
        tangent[np.ix_(dofs, dofs)] += transform.T @ geometric @ transform
    return tangent, axial_forces


def _geometric_stiffness_unit(length: float) -> np.ndarray:
    """Euler-Bernoulli geometric stiffness per unit tensile axial force."""
    beam = np.asarray(
        [[36.0, 3.0 * length, -36.0, 3.0 * length],
         [3.0 * length, 4.0 * length**2, -3.0 * length, -length**2],
         [-36.0, -3.0 * length, 36.0, -3.0 * length],
         [3.0 * length, -length**2, -3.0 * length, 4.0 * length**2]],
        dtype=float,
    ) / (30.0 * length)
    result = np.zeros((6, 6), dtype=float)
    result[np.ix_((1, 2, 4, 5), (1, 2, 4, 5))] = beam
    return result


def _local_stiffness(member: FrameMember, length: float) -> np.ndarray:
    material, section = member.material, member.section
    ea_l = material.youngs_modulus_pa * section.area_m2 / length
    ei = material.youngs_modulus_pa * section.second_moment_local_z_m4
    phi = 0.0
    if section.shear_area_local_y_m2 is not None:
        phi = 12.0 * ei / (material.shear_modulus_pa * section.shear_area_local_y_m2 * length**2)
    scale = 1.0 / (1.0 + phi)
    bending = scale * np.array(
        [[12.0, 6.0 * length, -12.0, 6.0 * length],
         [6.0 * length, (4.0 + phi) * length**2, -6.0 * length, (2.0 - phi) * length**2],
         [-12.0, -6.0 * length, 12.0, -6.0 * length],
         [6.0 * length, (2.0 - phi) * length**2, -6.0 * length, (4.0 + phi) * length**2]]
    ) * ei / length**3
    result = np.zeros((6, 6), dtype=float)
    result[np.ix_((0, 3), (0, 3))] = ea_l * np.array([[1.0, -1.0], [-1.0, 1.0]])
    result[np.ix_((1, 2, 4, 5), (1, 2, 4, 5))] = bending
    return result


def _local_mass(member: FrameMember, length: float) -> np.ndarray:
    mass_per_length = float(member.mass_per_length_kg_m or 0.0)
    scale = mass_per_length * length / 420.0
    result = np.zeros((6, 6), dtype=float)
    result[np.ix_((0, 3), (0, 3))] = mass_per_length * length / 6.0 * np.array([[2.0, 1.0], [1.0, 2.0]])
    beam = np.array(
        [[156.0, 22.0 * length, 54.0, -13.0 * length],
         [22.0 * length, 4.0 * length**2, 13.0 * length, -3.0 * length**2],
         [54.0, 13.0 * length, 156.0, -22.0 * length],
         [-13.0 * length, -3.0 * length**2, -22.0 * length, 4.0 * length**2]]
    )
    result[np.ix_((1, 2, 4, 5), (1, 2, 4, 5))] = scale * beam
    return result


def _transformation(cosine: float, sine: float) -> np.ndarray:
    result = np.zeros((6, 6), dtype=float)
    block = np.array([[cosine, sine, 0.0], [-sine, cosine, 0.0], [0.0, 0.0, 1.0]])
    result[:3, :3] = block
    result[3:, 3:] = block
    return result


def _equivalent_local_load(member: FrameMember, length: float) -> np.ndarray:
    qx, qy = member.uniform_load_local_x_n_m, member.uniform_load_local_y_n_m
    return np.asarray((qx * length / 2.0, qy * length / 2.0, qy * length**2 / 12.0,
                       qx * length / 2.0, qy * length / 2.0, -qy * length**2 / 12.0), dtype=float)


def _node_rows(values: np.ndarray) -> tuple[tuple[float, float, float], ...]:
    return tuple(tuple(float(value) for value in row) for row in values.reshape((-1, 3)))
