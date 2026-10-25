"""Small, explicit linear 3D truss and frame analysis.

This first 3D formulation uses prismatic Euler-Bernoulli frame members,
ideal supports and nodal loads. Member local x follows i-to-j; an explicit
local-y reference vector defines the remaining local axes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Sequence, cast

import numpy as np

from ._validation import finite as _finite
from ._validation import positive as _positive


def _index(name: str, value: int) -> int:
    if isinstance(value, bool) or int(value) != value or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return int(value)


@dataclass(frozen=True)
class FrameNode3D:
    x_m: float
    y_m: float
    z_m: float

    def __post_init__(self) -> None:
        for name in ("x_m", "y_m", "z_m"):
            object.__setattr__(self, name, _finite(name, getattr(self, name)))


@dataclass(frozen=True)
class FrameMaterial3D:
    youngs_modulus_pa: float
    shear_modulus_pa: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "youngs_modulus_pa", _positive("youngs_modulus_pa", self.youngs_modulus_pa)
        )
        object.__setattr__(
            self, "shear_modulus_pa", _positive("shear_modulus_pa", self.shear_modulus_pa)
        )


@dataclass(frozen=True)
class FrameSection3D:
    area_m2: float
    second_moment_y_m4: float
    second_moment_z_m4: float
    torsion_constant_m4: float

    def __post_init__(self) -> None:
        for name in ("area_m2", "second_moment_y_m4", "second_moment_z_m4", "torsion_constant_m4"):
            object.__setattr__(self, name, _positive(name, getattr(self, name)))


@dataclass(frozen=True)
class FrameMember3D:
    node_i: int
    node_j: int
    material: FrameMaterial3D
    section: FrameSection3D
    local_y_reference: Sequence[float] = (0.0, 1.0, 0.0)
    mass_per_length_kg_m: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_i", _index("node_i", self.node_i))
        object.__setattr__(self, "node_j", _index("node_j", self.node_j))
        if self.node_i == self.node_j:
            raise ValueError("a 3D frame member must connect two different nodes")
        if not isinstance(self.material, FrameMaterial3D) or not isinstance(
            self.section, FrameSection3D
        ):
            raise TypeError("material and section must be FrameMaterial3D and FrameSection3D")
        axis = np.asarray(self.local_y_reference, dtype=float)
        if axis.shape != (3,) or not np.all(np.isfinite(axis)) or np.linalg.norm(axis) == 0.0:
            raise ValueError("local_y_reference must be a finite non-zero 3-vector")
        object.__setattr__(self, "local_y_reference", tuple(float(v) for v in axis))
        mass = _finite("mass_per_length_kg_m", self.mass_per_length_kg_m)
        if mass < 0.0:
            raise ValueError("mass_per_length_kg_m must be non-negative")
        object.__setattr__(self, "mass_per_length_kg_m", mass)


@dataclass(frozen=True)
class TrussMember3D:
    node_i: int
    node_j: int
    youngs_modulus_pa: float
    area_m2: float
    mass_per_length_kg_m: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_i", _index("node_i", self.node_i))
        object.__setattr__(self, "node_j", _index("node_j", self.node_j))
        if self.node_i == self.node_j:
            raise ValueError("a 3D truss member must connect two different nodes")
        object.__setattr__(
            self, "youngs_modulus_pa", _positive("youngs_modulus_pa", self.youngs_modulus_pa)
        )
        object.__setattr__(self, "area_m2", _positive("area_m2", self.area_m2))
        mass = _finite("mass_per_length_kg_m", self.mass_per_length_kg_m)
        if mass < 0.0:
            raise ValueError("mass_per_length_kg_m must be non-negative")
        object.__setattr__(self, "mass_per_length_kg_m", mass)


@dataclass(frozen=True)
class StructuralModel3D:
    nodes: Sequence[FrameNode3D]
    members: Sequence[FrameMember3D | TrussMember3D]
    restraints: Sequence[Sequence[bool]]
    nodal_loads: Sequence[Sequence[float]] = ()
    nodal_lumped_masses_kg: Sequence[float] = ()

    def __post_init__(self) -> None:
        nodes, members = tuple(self.nodes), tuple(self.members)
        if not nodes or any(not isinstance(node, FrameNode3D) for node in nodes):
            raise ValueError("nodes must contain at least one FrameNode3D")
        if not members or any(
            not isinstance(member, (FrameMember3D, TrussMember3D)) for member in members
        ):
            raise ValueError("members must contain FrameMember3D or TrussMember3D instances")
        if any(max(member.node_i, member.node_j) >= len(nodes) for member in members):
            raise ValueError("member node indices must refer to nodes in the model")
        restraints = tuple(tuple(row) for row in self.restraints)
        if len(restraints) != len(nodes) or any(len(row) != 6 for row in restraints):
            raise ValueError("restraints must have one six-boolean row per node")
        if any(not isinstance(v, (bool, np.bool_)) for row in restraints for v in row):
            raise TypeError("restraint values must be booleans")
        restraints = tuple(tuple(bool(v) for v in row) for row in restraints)
        if len(self.nodal_loads):
            loads = tuple(tuple(_finite("nodal load", v) for v in row) for row in self.nodal_loads)
            if len(loads) != len(nodes) or any(len(row) != 6 for row in loads):
                raise ValueError("nodal_loads must have one six-component row per node")
        else:
            loads = tuple((0.0,) * 6 for _ in nodes)
        if len(self.nodal_lumped_masses_kg):
            masses = tuple(_finite("nodal mass", v) for v in self.nodal_lumped_masses_kg)
            if len(masses) != len(nodes) or any(v < 0.0 for v in masses):
                raise ValueError(
                    "nodal_lumped_masses_kg must contain one non-negative value per node"
                )
        else:
            masses = (0.0,) * len(nodes)
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "members", members)
        object.__setattr__(self, "restraints", restraints)
        object.__setattr__(self, "nodal_loads", loads)
        object.__setattr__(self, "nodal_lumped_masses_kg", masses)


@dataclass(frozen=True)
class StaticAnalysis3DResult:
    displacements: tuple[tuple[float, float, float, float, float, float], ...]
    reactions: tuple[tuple[float, float, float, float, float, float], ...]
    strain_energy_j: float
    free_dof_residual_norm: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModalAnalysis3DResult:
    frequencies_hz: tuple[float, ...]
    mode_shapes: tuple[tuple[tuple[float, float, float, float, float, float], ...], ...]
    generalized_masses_kg: tuple[float, ...]
    notes: tuple[str, ...] = ("Lumped translational mass; rotary inertia omitted.",)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BucklingAnalysis3DResult:
    critical_load_factors: tuple[float, ...]
    mode_shapes: tuple[tuple[tuple[float, float, float, float, float, float], ...], ...]
    reference_member_axial_forces_n: tuple[float, ...]
    notes: tuple[str, ...] = (
        "Ideal linear eigenvalue estimate; imperfections and yielding omitted.",
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _element_basis(
    model: StructuralModel3D, member: FrameMember3D | TrussMember3D
) -> tuple[float, np.ndarray]:
    ni = np.array(
        [
            model.nodes[member.node_i].x_m,
            model.nodes[member.node_i].y_m,
            model.nodes[member.node_i].z_m,
        ]
    )
    nj = np.array(
        [
            model.nodes[member.node_j].x_m,
            model.nodes[member.node_j].y_m,
            model.nodes[member.node_j].z_m,
        ]
    )
    delta = nj - ni
    length = float(np.linalg.norm(delta))
    scale = max(1.0, float(np.max(np.abs(ni))), float(np.max(np.abs(nj))))
    if length <= np.finfo(float).eps * scale:
        raise ValueError("member length must be greater than zero at the model coordinate scale")
    ex = delta / length
    ref = np.asarray(
        member.local_y_reference if isinstance(member, FrameMember3D) else (0.0, 1.0, 0.0),
        dtype=float,
    )
    ey = ref - np.dot(ref, ex) * ex
    if np.linalg.norm(ey) <= 1e-10 * np.linalg.norm(ref):
        raise ValueError("local_y_reference must not be parallel to the member axis")
    ey /= np.linalg.norm(ey)
    ez = np.cross(ex, ey)
    return length, np.vstack((ex, ey, ez))


def _frame_local_stiffness(member: FrameMember3D, length: float) -> np.ndarray:
    material, section = member.material, member.section
    k = np.zeros((12, 12), dtype=float)
    axial = material.youngs_modulus_pa * section.area_m2 / length
    torsion = material.shear_modulus_pa * section.torsion_constant_m4 / length
    for indices, scalar in (((0, 6), axial), ((3, 9), torsion)):
        i, j = indices
        k[np.ix_((i, j), (i, j))] += scalar * np.array(((1.0, -1.0), (-1.0, 1.0)))

    def bending(ei: float, indices: tuple[int, int, int, int], signs: tuple[float, ...]) -> None:
        matrix = (
            ei
            / length**3
            * np.array(
                (
                    (12, 6 * length, -12, 6 * length),
                    (6 * length, 4 * length**2, -6 * length, 2 * length**2),
                    (-12, -6 * length, 12, -6 * length),
                    (6 * length, 2 * length**2, -6 * length, 4 * length**2),
                ),
                dtype=float,
            )
        )
        sign = np.diag(signs)
        k[np.ix_(indices, indices)] += sign @ matrix @ sign

    bending(material.youngs_modulus_pa * section.second_moment_z_m4, (1, 5, 7, 11), (1, 1, 1, 1))
    bending(material.youngs_modulus_pa * section.second_moment_y_m4, (2, 4, 8, 10), (1, -1, 1, -1))
    return k


def _element_stiffness(member: FrameMember3D | TrussMember3D, length: float) -> np.ndarray:
    if isinstance(member, FrameMember3D):
        return _frame_local_stiffness(member, length)
    k = np.zeros((12, 12), dtype=float)
    axial = member.youngs_modulus_pa * member.area_m2 / length
    k[np.ix_((0, 6), (0, 6))] = axial * np.array(((1.0, -1.0), (-1.0, 1.0)))
    return k


def _transform(basis: np.ndarray) -> np.ndarray:
    result = np.zeros((12, 12), dtype=float)
    for offset in (0, 3, 6, 9):
        result[offset : offset + 3, offset : offset + 3] = basis
    return result


def assemble_matrices_3d(model: StructuralModel3D) -> tuple[np.ndarray, np.ndarray]:
    """Assemble dense stiffness and lumped translational mass matrices."""
    if not isinstance(model, StructuralModel3D):
        raise TypeError("model must be a StructuralModel3D")
    size = 6 * len(model.nodes)
    stiffness = np.zeros((size, size), dtype=float)
    mass = np.zeros((size, size), dtype=float)
    for member in model.members:
        length, basis = _element_basis(model, member)
        transform = _transform(basis)
        local = _element_stiffness(member, length)
        dofs = np.r_[
            np.arange(6 * member.node_i, 6 * member.node_i + 6),
            np.arange(6 * member.node_j, 6 * member.node_j + 6),
        ]
        stiffness[np.ix_(dofs, dofs)] += transform.T @ local @ transform
        member_mass = member.mass_per_length_kg_m * length / 2.0
        for node in (member.node_i, member.node_j):
            for component in range(3):
                mass[6 * node + component, 6 * node + component] += member_mass
    for node, value in enumerate(model.nodal_lumped_masses_kg):
        for component in range(3):
            mass[6 * node + component, 6 * node + component] += value
    return stiffness, mass


def analyze_linear_static_3d(model: StructuralModel3D) -> StaticAnalysis3DResult:
    """Solve one first-order static load case for a 3D truss/frame model."""
    stiffness, _ = assemble_matrices_3d(model)
    restrained = np.asarray(model.restraints, dtype=bool).reshape(-1)
    free = np.flatnonzero(~restrained)
    if not len(free):
        raise ValueError("static analysis requires at least one free degree of freedom")
    load = np.asarray(model.nodal_loads, dtype=float).reshape(-1)
    displacement = np.zeros_like(load)
    try:
        displacement[free] = np.linalg.solve(stiffness[np.ix_(free, free)], load[free])
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "restrained 3D stiffness is singular; check supports and connectivity"
        ) from exc
    residual = stiffness @ displacement - load
    nodes = displacement.reshape((-1, 6))
    reactions = residual.reshape((-1, 6))
    return StaticAnalysis3DResult(
        displacements=cast(
            tuple[tuple[float, float, float, float, float, float], ...],
            tuple(tuple(float(v) for v in row) for row in nodes),
        ),
        reactions=cast(
            tuple[tuple[float, float, float, float, float, float], ...],
            tuple(tuple(float(v) for v in row) for row in reactions),
        ),
        strain_energy_j=float(0.5 * displacement @ stiffness @ displacement),
        free_dof_residual_norm=float(np.linalg.norm(residual[free])),
    )


def _condense_massless(
    k: np.ndarray, m: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    massful = np.flatnonzero(np.diag(m) > 0.0)
    massless = np.flatnonzero(np.diag(m) == 0.0)
    if not len(massful):
        raise ValueError("modal analysis requires positive mass on at least one free translation")
    if not len(massless):
        return k, m, massful, massless, np.empty((0, len(massful)))
    if np.any(m[np.ix_(massless, np.arange(m.shape[0]))] != 0.0):
        raise ValueError("zero-mass degrees of freedom have non-zero mass coupling")
    kzz, kzm = k[np.ix_(massless, massless)], k[np.ix_(massless, massful)]
    try:
        recovery = -np.linalg.solve(kzz, kzm)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "zero-mass degrees of freedom cannot be condensed; check mechanisms"
        ) from exc
    reduced_k = k[np.ix_(massful, massful)] + k[np.ix_(massful, massless)] @ recovery
    return reduced_k, m[np.ix_(massful, massful)], massful, massless, recovery


def analyze_modes_3d(model: StructuralModel3D, *, mode_count: int = 6) -> ModalAnalysis3DResult:
    """Solve undamped generalized modes with lumped translational mass."""
    if isinstance(mode_count, bool) or int(mode_count) != mode_count or mode_count < 1:
        raise ValueError("mode_count must be a positive integer")
    stiffness, mass = assemble_matrices_3d(model)
    restrained = np.asarray(model.restraints, dtype=bool).reshape(-1)
    free = np.flatnonzero(~restrained)
    if not len(free):
        raise ValueError("modal analysis requires at least one free degree of freedom")
    kff, mff = stiffness[np.ix_(free, free)], mass[np.ix_(free, free)]
    kr, mr, massful, massless, recovery = _condense_massless(kff, mff)
    try:
        lower = np.linalg.cholesky(mr)
    except np.linalg.LinAlgError as exc:
        raise ValueError("modal mass matrix must be positive definite on massful degrees") from exc
    transformed = np.linalg.solve(lower, kr)
    symmetric = np.linalg.solve(lower, transformed.T).T
    eig, vectors = np.linalg.eigh(0.5 * (symmetric + symmetric.T))
    scale = max(float(np.max(np.abs(eig))), np.finfo(float).tiny)
    if float(np.min(eig)) < -1e-10 * scale:
        raise ValueError("3D frame stiffness has a negative eigenvalue; model is unstable")
    eig = np.maximum(eig, 0.0)
    selected = np.argsort(eig)[: min(int(mode_count), len(eig))]
    frequencies, shapes, generalized = [], [], []
    for index in selected:
        massful_shape = np.linalg.solve(lower.T, vectors[:, index])
        massful_norm = float(massful_shape @ mr @ massful_shape)
        if massful_norm <= 0.0:
            continue
        massful_shape /= math.sqrt(massful_norm)
        free_shape = np.zeros(len(free), dtype=float)
        free_shape[massful] = massful_shape
        if len(massless):
            free_shape[massless] = recovery @ massful_shape
        shape = np.zeros(stiffness.shape[0], dtype=float)
        shape[free] = free_shape
        peak = float(np.max(np.abs(shape.reshape((-1, 6))[:, :3])))
        if peak > 0:
            shape /= peak
        pivot = int(np.argmax(np.abs(shape)))
        if shape[pivot] < 0:
            shape *= -1
        frequencies.append(math.sqrt(float(eig[index])) / (2 * math.pi))
        shapes.append(
            cast(
                tuple[tuple[float, float, float, float, float, float], ...],
                tuple(tuple(float(v) for v in row) for row in shape.reshape((-1, 6))),
            )
        )
        generalized.append(float(free_shape @ mff @ free_shape))
    return ModalAnalysis3DResult(tuple(frequencies), tuple(shapes), tuple(generalized))


def analyze_linear_buckling_3d(
    model: StructuralModel3D, *, mode_count: int = 6
) -> BucklingAnalysis3DResult:
    """Estimate ideal elastic proportional buckling factors for a nodal load pattern."""
    if isinstance(mode_count, bool) or int(mode_count) != mode_count or mode_count < 1:
        raise ValueError("mode_count must be a positive integer")
    stiffness, _ = assemble_matrices_3d(model)
    load = np.asarray(model.nodal_loads, dtype=float).reshape(-1)
    restrained = np.asarray(model.restraints, dtype=bool).reshape(-1)
    free = np.flatnonzero(~restrained)
    if not len(free):
        raise ValueError("buckling analysis requires at least one free degree of freedom")
    try:
        displacement = np.zeros_like(load)
        displacement[free] = np.linalg.solve(stiffness[np.ix_(free, free)], load[free])
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "restrained 3D stiffness is singular; check supports and connectivity"
        ) from exc
    geometric = np.zeros_like(stiffness)
    axial_forces: list[float] = []
    for member in model.members:
        length, basis = _element_basis(model, member)
        dofs = np.r_[
            np.arange(6 * member.node_i, 6 * member.node_i + 6),
            np.arange(6 * member.node_j, 6 * member.node_j + 6),
        ]
        local_u = _transform(basis) @ displacement[dofs]
        if isinstance(member, TrussMember3D):
            force = member.youngs_modulus_pa * member.area_m2 / length * (local_u[6] - local_u[0])
            g = np.zeros((12, 12), dtype=float)
            for offset in (1, 2):
                g[np.ix_((offset, offset + 6), (offset, offset + 6))] += (
                    np.array(((1, -1), (-1, 1))) / length
                )
        else:
            force = (
                member.material.youngs_modulus_pa
                * member.section.area_m2
                / length
                * (local_u[6] - local_u[0])
            )
            g = np.zeros((12, 12), dtype=float)
            plane = np.array(
                (
                    (36, 3 * length, -36, 3 * length),
                    (3 * length, 4 * length**2, -3 * length, -(length**2)),
                    (-36, -3 * length, 36, -3 * length),
                    (3 * length, -(length**2), -3 * length, 4 * length**2),
                ),
                dtype=float,
            ) / (30 * length)
            g[np.ix_((1, 5, 7, 11), (1, 5, 7, 11))] += plane
            sign = np.diag((1, -1, 1, -1))
            g[np.ix_((2, 4, 8, 10), (2, 4, 8, 10))] += sign @ plane @ sign
        axial_forces.append(float(force))
        # Compression (negative axial force) destabilizes; solve K phi = lambda*(-N G) phi.
        geometric[np.ix_(dofs, dofs)] += _transform(basis).T @ (-force * g) @ _transform(basis)
    kff, gff = stiffness[np.ix_(free, free)], geometric[np.ix_(free, free)]
    try:
        lower = np.linalg.cholesky(kff)
    except np.linalg.LinAlgError as exc:
        raise ValueError(
            "buckling requires positive-definite restrained material stiffness"
        ) from exc
    left = np.linalg.solve(lower, gff)
    transformed = np.linalg.solve(lower, left.T).T
    eig, vectors = np.linalg.eigh(0.5 * (transformed + transformed.T))
    scale = max(float(np.max(np.abs(eig))), np.finfo(float).tiny)
    selected = [int(i) for i in np.argsort(eig)[::-1] if eig[i] > 1e-12 * scale]
    if not selected:
        raise ValueError("reference load pattern has no positive buckling factor")
    factors, shapes = [], []
    for index in selected[: int(mode_count)]:
        shape_free = np.linalg.solve(lower.T, vectors[:, index])
        shape = np.zeros(stiffness.shape[0])
        shape[free] = shape_free
        node_shape = shape.reshape((-1, 6))
        peak = float(np.max(np.abs(node_shape[:, :3])))
        if peak > 0:
            shape /= peak
        pivot = int(np.argmax(np.abs(shape)))
        if shape[pivot] < 0:
            shape *= -1
        factors.append(1.0 / float(eig[index]))
        shapes.append(
            cast(
                tuple[tuple[float, float, float, float, float, float], ...],
                tuple(tuple(float(v) for v in row) for row in shape.reshape((-1, 6))),
            )
        )
    return BucklingAnalysis3DResult(tuple(factors), tuple(shapes), tuple(axial_forces))


__all__ = [
    "FrameNode3D",
    "FrameMaterial3D",
    "FrameSection3D",
    "FrameMember3D",
    "TrussMember3D",
    "StructuralModel3D",
    "StaticAnalysis3DResult",
    "ModalAnalysis3DResult",
    "BucklingAnalysis3DResult",
    "assemble_matrices_3d",
    "analyze_linear_static_3d",
    "analyze_modes_3d",
    "analyze_linear_buckling_3d",
]
