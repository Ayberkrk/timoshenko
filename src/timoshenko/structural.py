"""Small, explicit 2D elastic frame models and analysis routines.

The implementation uses a direct-stiffness frame formulation with three
degrees of freedom per node: global x translation, global y translation and
rotation about global z. Models use SI units throughout.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Literal, Sequence

import numpy as np

from ._validation import finite as _finite
from ._validation import positive as _positive
from .polygon import PolygonSectionProperties
from .sections import SectionProperties


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
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
    """Linear-elastic E and G, with optional isotropic Poisson-ratio check."""

    youngs_modulus_pa: float
    shear_modulus_pa: float
    poisson_ratio: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "youngs_modulus_pa", _positive("youngs_modulus_pa", self.youngs_modulus_pa))
        object.__setattr__(self, "shear_modulus_pa", _positive("shear_modulus_pa", self.shear_modulus_pa))
        if self.poisson_ratio is not None:
            ratio = _finite("poisson_ratio", self.poisson_ratio)
            if not -1.0 < ratio < 0.5:
                raise ValueError("poisson_ratio must be between -1 and 0.5 for an isotropic elastic material")
            expected_shear = self.youngs_modulus_pa / (2.0 * (1.0 + ratio))
            if not math.isclose(self.shear_modulus_pa, expected_shear, rel_tol=2e-3):
                raise ValueError("youngs_modulus_pa, shear_modulus_pa and poisson_ratio are inconsistent")
            object.__setattr__(self, "poisson_ratio", ratio)


@dataclass(frozen=True)
class FrameSection:
    """Frame section data for a member in the x-y plane.

    ``second_moment_local_z_m4`` is the second moment for bending in the
    frame plane. ``shear_area_local_y_m2`` is an effective shear area. Leave
    it as ``None`` for Euler-Bernoulli bending; supply a verified effective
    area to use the Timoshenko shear-flexible stiffness. Optional section
    moduli at the positive and negative local-y edges enable approximate
    elastic normal stress recovery at member ends.
    """

    area_m2: float
    second_moment_local_z_m4: float
    shear_area_local_y_m2: float | None = None
    section_modulus_at_positive_local_y_m3: float | None = None
    section_modulus_at_negative_local_y_m3: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "area_m2", _positive("area_m2", self.area_m2))
        object.__setattr__(
            self,
            "second_moment_local_z_m4",
            _positive("second_moment_local_z_m4", self.second_moment_local_z_m4),
        )
        if self.shear_area_local_y_m2 is not None:
            object.__setattr__(self, "shear_area_local_y_m2", _positive("shear_area_local_y_m2", self.shear_area_local_y_m2))
        moduli = (self.section_modulus_at_positive_local_y_m3, self.section_modulus_at_negative_local_y_m3)
        if (moduli[0] is None) != (moduli[1] is None):
            raise ValueError("both local-y section moduli must be supplied together")
        for name, value in zip(("section_modulus_at_positive_local_y_m3", "section_modulus_at_negative_local_y_m3"), moduli, strict=True):
            if value is not None:
                object.__setattr__(self, name, _positive(name, value))

    @classmethod
    def from_properties(
        cls,
        properties: SectionProperties | PolygonSectionProperties,
        *,
        bending_axis: Literal["x", "y", "z"],
        shear_area_local_y_m2: float | None = None,
    ) -> FrameSection:
        """Build a frame section from geometric properties.

        ``bending_axis`` selects the section's principal moment axis to map to
        the member's local-z bending axis. It has no default because the axis
        names differ between the two property types: use ``"y"`` or ``"z"``
        for ``SectionProperties`` and ``"x"`` or ``"y"`` for
        ``PolygonSectionProperties``. Polygon properties are accepted only
        when their x/y axes are principal (their product moment is zero within
        floating-point roundoff). The effective shear area is never inferred.
        """
        if isinstance(properties, SectionProperties):
            if bending_axis == "y":
                second_moment = properties.second_moment_y_m4
                section_modulus_positive = section_modulus_negative = properties.section_modulus_y_m3
            elif bending_axis == "z":
                second_moment = properties.second_moment_z_m4
                section_modulus_positive = section_modulus_negative = properties.section_modulus_z_m3
            else:
                raise ValueError("bending_axis must be 'y' or 'z' for SectionProperties")
        elif isinstance(properties, PolygonSectionProperties):
            if bending_axis not in ("x", "y"):
                raise ValueError("bending_axis must be 'x' or 'y' for PolygonSectionProperties")
            inertia_x = float(properties.second_moment_x_m4)
            inertia_y = float(properties.second_moment_y_m4)
            product_moment = float(properties.product_moment_xy_m4)
            if (
                not all(math.isfinite(value) for value in (inertia_x, inertia_y, product_moment))
                or inertia_x <= 0.0
                or inertia_y <= 0.0
            ):
                raise ValueError("polygon section properties must have finite positive second moments")
            roundoff_tolerance = 1e-9 * math.sqrt(inertia_x * inertia_y)
            if abs(product_moment) > roundoff_tolerance:
                raise ValueError("polygon section x/y axes must be principal (product moment must be zero)")
            if bending_axis == "x":
                second_moment = inertia_x
                section_modulus_positive = properties.section_modulus_x_positive_m3
                section_modulus_negative = properties.section_modulus_x_negative_m3
            else:
                second_moment = inertia_y
                section_modulus_positive = properties.section_modulus_y_positive_m3
                section_modulus_negative = properties.section_modulus_y_negative_m3
        else:
            raise TypeError("properties must be SectionProperties or PolygonSectionProperties")
        return cls(
            area_m2=properties.area_m2,
            second_moment_local_z_m4=second_moment,
            shear_area_local_y_m2=shear_area_local_y_m2,
            section_modulus_at_positive_local_y_m3=section_modulus_positive,
            section_modulus_at_negative_local_y_m3=section_modulus_negative,
        )


@dataclass(frozen=True)
class FramePointLoad:
    """A concentrated member load at a local distance from node i."""

    distance_from_i_m: float
    force_local_x_n: float = 0.0
    force_local_y_n: float = 0.0
    moment_local_z_n_m: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "distance_from_i_m", _finite("distance_from_i_m", self.distance_from_i_m))
        object.__setattr__(self, "force_local_x_n", _finite("force_local_x_n", self.force_local_x_n))
        object.__setattr__(self, "force_local_y_n", _finite("force_local_y_n", self.force_local_y_n))
        object.__setattr__(self, "moment_local_z_n_m", _finite("moment_local_z_n_m", self.moment_local_z_n_m))


def _node_index(name: str, value: int) -> int:
    if isinstance(value, bool) or int(value) != value or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return int(value)


@dataclass(frozen=True)
class FrameMember:
    """A prismatic two-node frame member with local loads and end releases.

    ``uniform_load_local_x_n_m`` and ``uniform_load_local_y_n_m`` are
    positive in the member's local axes. Point loads use the same local axes.
    ``mass_per_length_kg_m`` is used by modal analysis and is not inferred
    from material or section data.
    """

    node_i: int
    node_j: int
    material: FrameMaterial
    section: FrameSection
    uniform_load_local_x_n_m: float = 0.0
    uniform_load_local_y_n_m: float = 0.0
    mass_per_length_kg_m: float | None = None
    point_loads: Sequence[FramePointLoad] = ()
    release_rotation_i: bool = False
    release_rotation_j: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_i", _node_index("node_i", self.node_i))
        object.__setattr__(self, "node_j", _node_index("node_j", self.node_j))
        if self.node_i == self.node_j:
            raise ValueError("a frame member must connect two different nodes")
        if not isinstance(self.material, FrameMaterial) or not isinstance(self.section, FrameSection):
            raise TypeError("material and section must be FrameMaterial and FrameSection instances")
        object.__setattr__(self, "uniform_load_local_x_n_m", _finite("uniform_load_local_x_n_m", self.uniform_load_local_x_n_m))
        object.__setattr__(self, "uniform_load_local_y_n_m", _finite("uniform_load_local_y_n_m", self.uniform_load_local_y_n_m))
        point_loads = tuple(self.point_loads)
        if any(not isinstance(load, FramePointLoad) for load in point_loads):
            raise TypeError("point_loads must contain FramePointLoad instances")
        if not isinstance(self.release_rotation_i, bool) or not isinstance(self.release_rotation_j, bool):
            raise TypeError("rotation releases must be booleans")
        object.__setattr__(self, "point_loads", point_loads)
        if self.mass_per_length_kg_m is not None:
            value = _finite("mass_per_length_kg_m", self.mass_per_length_kg_m)
            if value < 0.0:
                raise ValueError("mass_per_length_kg_m must be non-negative")
            object.__setattr__(self, "mass_per_length_kg_m", value)


@dataclass(frozen=True)
class AxialMember:
    """A two-node, prismatic axial bar for planar truss models."""

    node_i: int
    node_j: int
    youngs_modulus_pa: float
    area_m2: float
    uniform_load_local_x_n_m: float = 0.0
    mass_per_length_kg_m: float | None = None
    point_loads: Sequence[FramePointLoad] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_i", _node_index("node_i", self.node_i))
        object.__setattr__(self, "node_j", _node_index("node_j", self.node_j))
        if self.node_i == self.node_j:
            raise ValueError("an axial member must connect two different nodes")
        object.__setattr__(self, "youngs_modulus_pa", _positive("youngs_modulus_pa", self.youngs_modulus_pa))
        object.__setattr__(self, "area_m2", _positive("area_m2", self.area_m2))
        object.__setattr__(self, "uniform_load_local_x_n_m", _finite("uniform_load_local_x_n_m", self.uniform_load_local_x_n_m))
        if self.mass_per_length_kg_m is not None:
            value = _finite("mass_per_length_kg_m", self.mass_per_length_kg_m)
            if value < 0.0:
                raise ValueError("mass_per_length_kg_m must be non-negative")
            object.__setattr__(self, "mass_per_length_kg_m", value)
        point_loads = tuple(self.point_loads)
        if any(not isinstance(load, FramePointLoad) for load in point_loads):
            raise TypeError("point_loads must contain FramePointLoad instances")
        if any(load.force_local_y_n != 0.0 or load.moment_local_z_n_m != 0.0 for load in point_loads):
            raise ValueError("axial members only support local axial point loads")
        object.__setattr__(self, "point_loads", point_loads)


@dataclass(frozen=True)
class StructuralModel:
    """A planar frame or axial-truss model with nodal loads and supports.

    Each restraint row is ``(fix_x, fix_y, fix_rotation)``. Each load row is
    ``(Fx_N, Fy_N, Mz_Nm)``. Nodal lumped masses contribute equally to the
    two translational degrees of freedom; member mass is supplied separately
    as mass per unit length. Prescribed movements may be assigned to
    restrained degrees of freedom.
    """

    nodes: Sequence[FrameNode]
    members: Sequence[FrameMember | AxialMember]
    restraints: Sequence[Sequence[bool]]
    nodal_loads: Sequence[Sequence[float]] = ()
    nodal_lumped_masses_kg: Sequence[float] = ()
    prescribed_displacements: Sequence[Sequence[float | None]] = ()

    def __post_init__(self) -> None:
        nodes = tuple(self.nodes)
        members = tuple(self.members)
        if not nodes:
            raise ValueError("a structural model must contain at least one node")
        if any(not isinstance(node, FrameNode) for node in nodes):
            raise TypeError("nodes must contain FrameNode instances")
        if not members or any(not isinstance(member, (FrameMember, AxialMember)) for member in members):
            raise ValueError("members must contain FrameMember or AxialMember instances")
        if any(max(member.node_i, member.node_j) >= len(nodes) for member in members):
            raise ValueError("member node indices must refer to nodes in the model")
        restraints = tuple(tuple(row) for row in self.restraints)
        if len(restraints) != len(nodes) or any(len(row) != 3 for row in restraints):
            raise ValueError("restraints must have one (fix_x, fix_y, fix_rotation) row per node")
        if any(not isinstance(value, (bool, np.bool_)) for row in restraints for value in row):
            raise TypeError("restraint values must be booleans")
        restraints = tuple(tuple(bool(value) for value in row) for row in restraints)
        if len(self.prescribed_displacements):
            prescribed = tuple(tuple(value for value in row) for row in self.prescribed_displacements)
            if len(prescribed) != len(nodes) or any(len(row) != 3 for row in prescribed):
                raise ValueError("prescribed_displacements must have one (x_m, y_m, rotation_rad) row per node")
            normalized_prescribed = []
            for node_index, row in enumerate(prescribed):
                values: list[float | None] = []
                for dof, value in enumerate(row):
                    if restraints[node_index][dof]:
                        values.append(0.0 if value is None else _finite("prescribed displacement", value))
                    elif value is not None:
                        raise ValueError("prescribed displacements can only be set on restrained degrees of freedom")
                    else:
                        values.append(None)
                normalized_prescribed.append(tuple(values))
            prescribed = tuple(normalized_prescribed)
        else:
            prescribed = tuple(tuple(0.0 if fix else None for fix in row) for row in restraints)
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
        object.__setattr__(self, "prescribed_displacements", prescribed)


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
    member_end_normal_stresses_pa: tuple[tuple[float, float, float, float] | None, ...] = ()
    global_equilibrium_residual: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True)
class ModalAnalysisResult:
    """Natural frequencies and peak-normalized mode shapes of a frame model."""

    frequencies_hz: tuple[float, ...]
    mode_shapes: tuple[tuple[tuple[float, float, float], ...], ...]
    generalized_masses_kg: tuple[float, ...]
    constrained_dof_count: int
    notes: tuple[str, ...] = ()
    participation_factors_x: tuple[float, ...] = ()
    participation_factors_y: tuple[float, ...] = ()
    effective_modal_masses_x_kg: tuple[float, ...] = ()
    effective_modal_masses_y_kg: tuple[float, ...] = ()
    effective_modal_mass_ratios_x: tuple[float, ...] = ()
    effective_modal_mass_ratios_y: tuple[float, ...] = ()
    total_participating_mass_x_kg: float = 0.0
    total_participating_mass_y_kg: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True)
class BucklingAnalysisResult:
    """Linear eigenvalue buckling factors and associated frame shapes."""

    critical_load_factors: tuple[float, ...]
    mode_shapes: tuple[tuple[tuple[float, float, float], ...], ...]
    reference_member_axial_forces_n: tuple[float, ...]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


def analyze_linear_static(model: StructuralModel) -> FrameAnalysisResult:
    """Solve one small-displacement, linear-elastic 2D frame load case.

    Uniform and concentrated member loads are expressed in local member
    coordinates. Supports are ideal restraints. The routine does not perform
    design-code checks, load combinations, geometric nonlinearity or 3D
    analysis.
    """
    if not isinstance(model, StructuralModel):
        raise TypeError("model must be a StructuralModel")
    stiffness, load, element_data = _assemble(model, include_member_loads=True)
    restrained, prescribed = _constraint_arrays(model)
    free = np.flatnonzero(~restrained)
    displacements = prescribed.copy()
    if len(free):
        try:
            right_hand_side = load[free] - stiffness[np.ix_(free, np.flatnonzero(restrained))] @ prescribed[restrained]
            displacements[free] = np.linalg.solve(stiffness[np.ix_(free, free)], right_hand_side)
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
    member_forces: list[tuple[float, float, float, float, float, float]] = []
    for member_index, _member in enumerate(model.members):
        dofs, transform, local_stiffness, equivalent_load, _, _, _ = element_data[member_index]
        local_displacement = transform @ displacements[dofs]
        end_force = local_stiffness @ local_displacement - equivalent_load
        member_forces.append(_end_actions(end_force))
    member_stresses = tuple(
        _member_end_normal_stress(member, end_force)
        for member, end_force in zip(model.members, member_forces, strict=True)
    )
    energy = 0.5 * float(displacements @ stiffness @ displacements)
    return FrameAnalysisResult(
        displacements=_node_rows(displacements),
        reactions=_node_rows(reactions),
        member_end_forces_local=tuple(member_forces),
        strain_energy_j=energy,
        free_dof_residual_norm=residual_norm,
        member_end_normal_stresses_pa=member_stresses,
        global_equilibrium_residual=_global_equilibrium_residual(model, load + residual, displacements),
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
    if any(isinstance(member, FrameMember) and (member.release_rotation_i or member.release_rotation_j) for member in model.members):
        raise ValueError("P-delta analysis does not support frame members with rotational end releases")
    if isinstance(maximum_iterations, bool) or int(maximum_iterations) != maximum_iterations or maximum_iterations < 1:
        raise ValueError("maximum_iterations must be a positive integer")
    tolerance = _positive("tolerance", tolerance)
    relaxation = _finite("relaxation", relaxation)
    if not 0.0 < relaxation <= 1.0:
        raise ValueError("relaxation must be in (0, 1]")
    material_stiffness, load, element_data = _assemble(model, include_member_loads=True)
    restrained, prescribed = _constraint_arrays(model)
    free = np.flatnonzero(~restrained)
    if not len(free):
        displacement = prescribed.copy()
    else:
        try:
            displacement = prescribed.copy()
            right_hand_side = load[free] - material_stiffness[np.ix_(free, np.flatnonzero(restrained))] @ prescribed[restrained]
            displacement[free] = np.linalg.solve(material_stiffness[np.ix_(free, free)], right_hand_side)
        except np.linalg.LinAlgError as exc:
            raise ValueError("the restrained frame stiffness is singular; check supports and member connectivity") from exc
    converged_iteration = 0
    tangent = material_stiffness
    for iteration in range(1, int(maximum_iterations) + 1):
        tangent, axial_forces = _p_delta_tangent(model, material_stiffness, element_data, displacement)
        trial = np.zeros_like(displacement)
        trial[restrained] = prescribed[restrained]
        if len(free):
            eigenvalues = np.linalg.eigvalsh(tangent[np.ix_(free, free)])
            stiffness_scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
            if float(np.min(eigenvalues)) < -1e-12 * stiffness_scale:
                raise ValueError("P-delta tangent stiffness indicates frame instability")
            try:
                right_hand_side = load[free] - tangent[np.ix_(free, np.flatnonzero(restrained))] @ prescribed[restrained]
                trial[free] = np.linalg.solve(tangent[np.ix_(free, free)], right_hand_side)
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
    member_forces: list[tuple[float, float, float, float, float, float]] = []
    for member, data, axial_tension in zip(model.members, element_data, axial_forces, strict=True):
        dofs, transform, local_stiffness, equivalent_load, length, _, _ = data
        local_displacement = transform @ displacement[dofs]
        end_force = local_stiffness @ local_displacement
        geometric = axial_tension * _geometric_stiffness_unit(length, member)
        if isinstance(member, FrameMember):
            geometric, _ = _condense_rotational_releases(member, geometric, np.zeros(6))
        end_force += geometric @ local_displacement
        end_force -= equivalent_load
        member_forces.append(_end_actions(end_force))
    member_stresses = tuple(
        _member_end_normal_stress(member, end_force)
        for member, end_force in zip(model.members, member_forces, strict=True)
    )
    strain_energy = 0.5 * float(displacement @ material_stiffness @ displacement)
    return FrameAnalysisResult(
        displacements=_node_rows(displacement),
        reactions=_node_rows(residual),
        member_end_forces_local=tuple(member_forces),
        strain_energy_j=strain_energy,
        free_dof_residual_norm=residual_norm,
        analysis_type="p_delta",
        iteration_count=converged_iteration,
        member_end_normal_stresses_pa=member_stresses,
        global_equilibrium_residual=_global_equilibrium_residual(model, load + residual, displacement, deformed_positions=True),
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
    if any(isinstance(member, FrameMember) and (member.release_rotation_i or member.release_rotation_j) for member in model.members):
        raise ValueError("modal analysis does not support frame members with rotational end releases")
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
    restrained, _ = _constraint_arrays(model)
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
    participation_x, participation_y = [], []
    effective_mass_x, effective_mass_y = [], []
    modal_mass_ratio_x, modal_mass_ratio_y = [], []
    influence_x = np.asarray([1.0 if dof % 3 == 0 else 0.0 for dof in free])
    influence_y = np.asarray([1.0 if dof % 3 == 1 else 0.0 for dof in free])
    total_mass_x = float(influence_x @ mff @ influence_x)
    total_mass_y = float(influence_y @ mff @ influence_y)
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
        generalized_mass = float(vector_free @ mff @ vector_free)
        generalized_masses.append(generalized_mass)
        gamma_x = float(vector_free @ mff @ influence_x) / generalized_mass
        gamma_y = float(vector_free @ mff @ influence_y) / generalized_mass
        effective_x, effective_y = gamma_x**2 * generalized_mass, gamma_y**2 * generalized_mass
        participation_x.append(gamma_x)
        participation_y.append(gamma_y)
        effective_mass_x.append(effective_x)
        effective_mass_y.append(effective_y)
        modal_mass_ratio_x.append(effective_x / total_mass_x if total_mass_x > 0.0 else 0.0)
        modal_mass_ratio_y.append(effective_y / total_mass_y if total_mass_y > 0.0 else 0.0)
    notes = ("Member rotary inertia and damping are omitted; member mass uses Euler-Bernoulli interpolation.",)
    return ModalAnalysisResult(
        frequencies_hz=tuple(frequencies),
        mode_shapes=tuple(shapes),
        generalized_masses_kg=tuple(generalized_masses),
        constrained_dof_count=int(np.count_nonzero(restrained)),
        notes=notes,
        participation_factors_x=tuple(participation_x),
        participation_factors_y=tuple(participation_y),
        effective_modal_masses_x_kg=tuple(effective_mass_x),
        effective_modal_masses_y_kg=tuple(effective_mass_y),
        effective_modal_mass_ratios_x=tuple(modal_mass_ratio_x),
        effective_modal_mass_ratios_y=tuple(modal_mass_ratio_y),
        total_participating_mass_x_kg=total_mass_x,
        total_participating_mass_y_kg=total_mass_y,
    )


def analyze_linear_buckling(model: StructuralModel, *, mode_count: int = 6) -> BucklingAnalysisResult:
    """Estimate elastic system buckling load factors for one reference load pattern.

    The reference axial forces come from a first-order static solution. The
    eigenproblem scales the complete nodal and member load pattern until the
    material stiffness and compressive geometric stiffness become singular.
    This ideal eigenvalue estimate omits imperfections, material yielding and
    post-buckling response.
    """
    if not isinstance(model, StructuralModel):
        raise TypeError("model must be a StructuralModel")
    if any(isinstance(member, FrameMember) and (member.release_rotation_i or member.release_rotation_j) for member in model.members):
        raise ValueError("buckling analysis does not support frame members with rotational end releases")
    if isinstance(mode_count, bool) or int(mode_count) != mode_count or mode_count < 1:
        raise ValueError("mode_count must be a positive integer")
    stiffness, load, element_data = _assemble(model, include_member_loads=True)
    restrained, prescribed = _constraint_arrays(model)
    if np.any(np.abs(prescribed[restrained]) > 0.0):
        raise ValueError("linear buckling requires zero prescribed support displacements")
    free = np.flatnonzero(~restrained)
    if not len(free):
        raise ValueError("linear buckling requires at least one unrestrained degree of freedom")
    displacement = prescribed.copy()
    try:
        displacement[free] = np.linalg.solve(stiffness[np.ix_(free, free)], load[free])
    except np.linalg.LinAlgError as exc:
        raise ValueError("the restrained frame stiffness is singular; check supports and connectivity") from exc
    _, axial_forces = _p_delta_tangent(model, stiffness, element_data, displacement)
    geometric = np.zeros_like(stiffness)
    for member, data, axial_tension in zip(model.members, element_data, axial_forces, strict=True):
        dofs, transform, _, _, length, _, _ = data
        local = -axial_tension * _geometric_stiffness_unit(length, member)
        if isinstance(member, FrameMember):
            local, _ = _condense_rotational_releases(member, local, np.zeros(6))
        geometric[np.ix_(dofs, dofs)] += transform.T @ local @ transform
    kff, gff = stiffness[np.ix_(free, free)], geometric[np.ix_(free, free)]
    try:
        lower = np.linalg.cholesky(kff)
    except np.linalg.LinAlgError as exc:
        raise ValueError("the restrained frame stiffness must be positive definite for buckling analysis") from exc
    left_solved = np.linalg.solve(lower, gff)
    symmetric = np.linalg.solve(lower, left_solved.T).T
    symmetric = 0.5 * (symmetric + symmetric.T)
    eigenvalues, transformed_modes = np.linalg.eigh(symmetric)
    scale = max(float(np.max(np.abs(eigenvalues))), np.finfo(float).tiny)
    positive = [index for index, value in enumerate(eigenvalues) if value > 1e-12 * scale]
    if not positive:
        raise ValueError("the reference load pattern has no positive elastic buckling factor")
    positive.sort(key=lambda index: 1.0 / float(eigenvalues[index]))
    factors, shapes = [], []
    for index in positive[: min(int(mode_count), len(positive))]:
        vector_free = np.linalg.solve(lower.T, transformed_modes[:, index])
        vector = np.zeros(stiffness.shape[0], dtype=float)
        vector[free] = vector_free
        translations = vector.reshape((-1, 3))[:, :2]
        peak = float(np.max(np.abs(translations)))
        if peak > 0.0:
            vector /= peak
        largest = int(np.argmax(np.abs(vector)))
        if vector[largest] < 0.0:
            vector *= -1.0
        factors.append(1.0 / float(eigenvalues[index]))
        shapes.append(_node_rows(vector))
    return BucklingAnalysisResult(
        critical_load_factors=tuple(factors),
        mode_shapes=tuple(shapes),
        reference_member_axial_forces_n=tuple(axial_forces),
        notes=("Ideal elastic eigenvalue estimate; imperfections, yielding and post-buckling response are omitted.",),
    )


def modal_assurance_criterion(
    reference_shape: Sequence[complex | float] | np.ndarray,
    observed_shape: Sequence[complex | float] | np.ndarray,
) -> float:
    """Return MAC for two same-length real or complex shape vectors.

    The caller must first map measured channels and model degrees of freedom
    into the same ordering and remove unavailable components.
    """
    reference = np.asarray(reference_shape, dtype=complex)
    observed = np.asarray(observed_shape, dtype=complex)
    if reference.ndim != 1 or observed.ndim != 1 or reference.size == 0 or reference.shape != observed.shape:
        raise ValueError("mode shapes must be non-empty one-dimensional vectors of equal length")
    if not np.all(np.isfinite(reference)) or not np.all(np.isfinite(observed)):
        raise ValueError("mode shape values must be finite")
    reference_mass = float(np.vdot(reference, reference).real)
    observed_mass = float(np.vdot(observed, observed).real)
    if reference_mass <= 0.0 or observed_mass <= 0.0:
        raise ValueError("mode shapes must have non-zero norm")
    mac = abs(np.vdot(reference, observed)) ** 2 / (reference_mass * observed_mass)
    return float(min(1.0, max(0.0, mac)))


def _assemble(
    model: StructuralModel,
    *,
    include_member_loads: bool,
) -> tuple[np.ndarray, np.ndarray, list[Any]]:
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
        member_load = _equivalent_local_load(member, length)
        equivalent_load = member_load if include_member_loads else np.zeros(6)
        if isinstance(member, FrameMember):
            local_stiffness, equivalent_load = _condense_rotational_releases(
                member, local_stiffness, equivalent_load
            )
        global_stiffness = transform.T @ local_stiffness @ transform
        stiffness[np.ix_(dofs, dofs)] += global_stiffness
        if include_member_loads:
            load[dofs] += transform.T @ equivalent_load
        element_data.append((dofs, transform, local_stiffness, equivalent_load, length, cosine, sine))
    if not np.all(np.isfinite(stiffness)) or not np.all(np.isfinite(load)):
        raise ValueError("assembled stiffness or load contains non-finite values")
    return stiffness, load, element_data


def _constraint_arrays(model: StructuralModel) -> tuple[np.ndarray, np.ndarray]:
    restrained = np.asarray(model.restraints, dtype=bool).reshape(-1)
    prescribed = np.asarray(
        [0.0 if value is None else value for row in model.prescribed_displacements for value in row],
        dtype=float,
    )
    active_rotation = [False] * len(model.nodes)
    for member in model.members:
        if isinstance(member, FrameMember):
            active_rotation[member.node_i] |= not member.release_rotation_i
            active_rotation[member.node_j] |= not member.release_rotation_j
    for node_index, is_active in enumerate(active_rotation):
        if is_active:
            continue
        rotation_dof = 3 * node_index + 2
        if not restrained[rotation_dof] and model.nodal_loads[node_index][2] != 0.0:
            raise ValueError("a nodal moment requires an unreleased frame member or a restrained rotation")
        restrained[rotation_dof] = True
    return restrained, prescribed


def _p_delta_tangent(
    model: StructuralModel,
    material_stiffness: np.ndarray,
    element_data: Sequence[Any],
    displacement: np.ndarray,
) -> tuple[np.ndarray, list[float]]:
    tangent = material_stiffness.copy()
    axial_forces = []
    for member, data in zip(model.members, element_data, strict=True):
        dofs, transform, local_stiffness, equivalent_load, length, _, _ = data
        local_displacement = transform @ displacement[dofs]
        material_end_force = local_stiffness @ local_displacement - equivalent_load
        axial_tension = float((material_end_force[3] - material_end_force[0]) / 2.0)
        axial_forces.append(axial_tension)
        geometric = axial_tension * _geometric_stiffness_unit(length, member)
        if isinstance(member, FrameMember):
            geometric, _ = _condense_rotational_releases(member, geometric, np.zeros(6))
        tangent[np.ix_(dofs, dofs)] += transform.T @ geometric @ transform
    return tangent, axial_forces


def _geometric_stiffness_unit(length: float, member: FrameMember | AxialMember) -> np.ndarray:
    """Geometric stiffness per unit tensile axial force."""
    if isinstance(member, AxialMember):
        result = np.zeros((6, 6), dtype=float)
        result[np.ix_((1, 4), (1, 4))] = np.array([[1.0, -1.0], [-1.0, 1.0]]) / length
        return result
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


def _condense_rotational_releases(
    member: FrameMember,
    stiffness: np.ndarray,
    load: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    released = tuple(index for index, flag in zip((2, 5), (member.release_rotation_i, member.release_rotation_j), strict=True) if flag)
    if not released:
        return stiffness, load
    retained = tuple(index for index in range(6) if index not in released)
    krr = stiffness[np.ix_(released, released)]
    kra = stiffness[np.ix_(released, retained)]
    kar = stiffness[np.ix_(retained, released)]
    kaa = stiffness[np.ix_(retained, retained)]
    reduced_stiffness = kaa - kar @ np.linalg.solve(krr, kra)
    reduced_load = load[list(retained)] - kar @ np.linalg.solve(krr, load[list(released)])
    result_stiffness, result_load = np.zeros((6, 6), dtype=float), np.zeros(6, dtype=float)
    result_stiffness[np.ix_(retained, retained)] = reduced_stiffness
    result_load[list(retained)] = reduced_load
    return result_stiffness, result_load


def _shear_parameter(member: FrameMember, length: float) -> float:
    """Ratio 12 E I / (G A_s L^2) of bending to shear stiffness; zero without a shear area."""
    material, section = member.material, member.section
    if section.shear_area_local_y_m2 is None:
        return 0.0
    ei = material.youngs_modulus_pa * section.second_moment_local_z_m4
    return 12.0 * ei / (material.shear_modulus_pa * section.shear_area_local_y_m2 * length**2)


def _local_stiffness(member: FrameMember | AxialMember, length: float) -> np.ndarray:
    if isinstance(member, AxialMember):
        result = np.zeros((6, 6), dtype=float)
        axial = member.youngs_modulus_pa * member.area_m2 / length
        result[np.ix_((0, 3), (0, 3))] = axial * np.array([[1.0, -1.0], [-1.0, 1.0]])
        return result
    material, section = member.material, member.section
    ea_l = material.youngs_modulus_pa * section.area_m2 / length
    ei = material.youngs_modulus_pa * section.second_moment_local_z_m4
    phi = _shear_parameter(member, length)
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


def _local_mass(member: FrameMember | AxialMember, length: float) -> np.ndarray:
    mass_per_length = float(member.mass_per_length_kg_m or 0.0)
    if isinstance(member, AxialMember):
        translational = mass_per_length * length / 6.0 * np.array([[2.0, 1.0], [1.0, 2.0]])
        result = np.zeros((6, 6), dtype=float)
        result[np.ix_((0, 3), (0, 3))] = translational
        result[np.ix_((1, 4), (1, 4))] = translational
        return result
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


def _equivalent_local_load(member: FrameMember | AxialMember, length: float) -> np.ndarray:
    qx = member.uniform_load_local_x_n_m
    result = np.zeros(6, dtype=float)
    result[0] = result[3] = qx * length / 2.0
    if isinstance(member, AxialMember):
        point_loads = member.point_loads
        for point in point_loads:
            location = point.distance_from_i_m
            if not 0.0 <= location <= length:
                raise ValueError("point load distance must lie between the member ends")
            ratio = location / length
            result[0] += point.force_local_x_n * (1.0 - ratio)
            result[3] += point.force_local_x_n * ratio
        return result
    qy = member.uniform_load_local_y_n_m
    result += np.asarray((0.0, qy * length / 2.0, qy * length**2 / 12.0,
                          0.0, qy * length / 2.0, -qy * length**2 / 12.0))
    # Shape functions of the shear-flexible member, consistent with
    # _local_stiffness: deflection for a force, section rotation for a moment.
    # Both reduce to the Hermite cubics when phi is zero.
    phi = _shear_parameter(member, length)
    for point in member.point_loads:
        location = point.distance_from_i_m
        if not 0.0 <= location <= length:
            raise ValueError("point load distance must lie between the member ends")
        ratio = location / length
        result[0] += point.force_local_x_n * (1.0 - ratio)
        result[3] += point.force_local_x_n * ratio
        shape = np.asarray((1.0 - 3 * ratio**2 + 2 * ratio**3 + phi * (1.0 - ratio),
                            length * (ratio - 2 * ratio**2 + ratio**3 + 0.5 * phi * (ratio - ratio**2)),
                            3 * ratio**2 - 2 * ratio**3 + phi * ratio,
                            length * (-ratio**2 + ratio**3 - 0.5 * phi * (ratio - ratio**2)))) / (1.0 + phi)
        result[np.asarray((1, 2, 4, 5))] += point.force_local_y_n * shape
        rotation = np.asarray(((-6 * ratio + 6 * ratio**2) / length,
                               1.0 - 4 * ratio + 3 * ratio**2 + phi * (1.0 - ratio),
                               (6 * ratio - 6 * ratio**2) / length,
                               -2 * ratio + 3 * ratio**2 + phi * ratio)) / (1.0 + phi)
        result[np.asarray((1, 2, 4, 5))] += point.moment_local_z_n_m * rotation
    return result


def _node_rows(values: np.ndarray) -> tuple[tuple[float, float, float], ...]:
    return tuple((float(x), float(y), float(rotation)) for x, y, rotation in values.reshape((-1, 3)))


def _end_actions(values: np.ndarray) -> tuple[float, float, float, float, float, float]:
    axial_i, shear_i, moment_i, axial_j, shear_j, moment_j = (float(value) for value in values)
    return axial_i, shear_i, moment_i, axial_j, shear_j, moment_j


def _global_equilibrium_residual(
    model: StructuralModel,
    nodal_resultants: np.ndarray,
    displacements: np.ndarray,
    *,
    deformed_positions: bool = False,
) -> tuple[float, float, float]:
    rows = nodal_resultants.reshape((-1, 3))
    force_x = float(np.sum(rows[:, 0]))
    force_y = float(np.sum(rows[:, 1]))
    displacement_rows = displacements.reshape((-1, 3))
    moment_z = 0.0
    for node, row, movement in zip(model.nodes, rows, displacement_rows, strict=True):
        x, y = node.x_m, node.y_m
        if deformed_positions:
            x += movement[0]
            y += movement[1]
        moment_z += x * row[1] - y * row[0] + row[2]
    return force_x, force_y, float(moment_z)


def _member_end_normal_stress(
    member: FrameMember | AxialMember,
    end_forces: Sequence[float],
) -> tuple[float, float, float, float] | None:
    if isinstance(member, AxialMember):
        stress_i = -float(end_forces[0]) / member.area_m2
        stress_j = float(end_forces[3]) / member.area_m2
        return stress_i, stress_i, stress_j, stress_j
    section = member.section
    positive = section.section_modulus_at_positive_local_y_m3
    negative = section.section_modulus_at_negative_local_y_m3
    if positive is None or negative is None:
        return None
    axial_i, axial_j = -float(end_forces[0]), float(end_forces[3])
    moment_i, moment_j = float(end_forces[2]), float(end_forces[5])
    stress_i_positive = axial_i / section.area_m2 + moment_i / positive
    stress_i_negative = axial_i / section.area_m2 - moment_i / negative
    stress_j_positive = axial_j / section.area_m2 - moment_j / positive
    stress_j_negative = axial_j / section.area_m2 + moment_j / negative
    return stress_i_positive, stress_i_negative, stress_j_positive, stress_j_negative
