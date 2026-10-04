import json
import math

import pytest

import timoshenko as tm

E = 200e9
G = E / (2 * (1 + 0.3))
AREA = 0.01
INERTIA = 8e-6
MATERIAL = tm.FrameMaterial(E, G)
SECTION = tm.FrameSection(AREA, INERTIA)


def cantilever(*, load_y_n=0.0, shear_area=None, distributed_y_n_m=0.0, mass_per_length=None):
    return tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(3.0, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, tm.FrameSection(AREA, INERTIA, shear_area),
            uniform_load_local_y_n_m=distributed_y_n_m,
            mass_per_length_kg_m=mass_per_length,
        ),),
        restraints=((True, True, True), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (0.0, load_y_n, 0.0)),
    )


def test_cantilever_tip_load_matches_closed_form_displacement_and_reaction():
    force, length = -12_000.0, 3.0
    result = tm.analyze_linear_static(cantilever(load_y_n=force))
    assert result.displacements[1][1] == pytest.approx(force * length**3 / (3 * E * INERTIA))
    assert result.displacements[1][2] == pytest.approx(force * length**2 / (2 * E * INERTIA))
    assert result.reactions[0][1] == pytest.approx(-force)
    assert result.free_dof_residual_norm < 1e-7
    assert result.global_equilibrium_residual == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)
    assert result.strain_energy_j == pytest.approx(0.5 * force * result.displacements[1][1])


def test_assembled_two_element_cantilever_matches_closed_form():
    length, force = 3.0, -12_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length / 2, 0.0), tm.FrameNode(length, 0.0)),
        members=(
            tm.FrameMember(0, 1, MATERIAL, SECTION),
            tm.FrameMember(1, 2, MATERIAL, SECTION),
        ),
        restraints=((True, True, True), (False, False, False), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, force, 0.0)),
    )
    result = tm.analyze_linear_static(model)
    assert result.displacements[2][1] == pytest.approx(force * length**3 / (3 * E * INERTIA))
    assert result.reactions[0][1] == pytest.approx(-force)


def test_cantilever_timoshenko_shear_deflection_matches_closed_form():
    force, length, shear_area = -12_000.0, 3.0, 0.008
    result = tm.analyze_linear_static(cantilever(load_y_n=force, shear_area=shear_area))
    expected = force * (length**3 / (3 * E * INERTIA) + length / (G * shear_area))
    assert result.displacements[1][1] == pytest.approx(expected, rel=1e-12)


def test_timoshenko_frame_approaches_euler_bernoulli_for_slender_member():
    length, force, shear_area = 30.0, -1_000.0, 0.008
    nodes = (tm.FrameNode(0.0, 0.0), tm.FrameNode(length / 2, 0.0), tm.FrameNode(length, 0.0))
    members = (
        tm.FrameMember(0, 1, MATERIAL, tm.FrameSection(AREA, INERTIA, shear_area)),
        tm.FrameMember(1, 2, MATERIAL, tm.FrameSection(AREA, INERTIA, shear_area)),
    )
    model = tm.StructuralModel(
        nodes=nodes,
        members=members,
        restraints=((True, True, True), (False, False, False), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, force, 0.0)),
    )
    result = tm.analyze_linear_static(model)
    euler_deflection = force * length**3 / (3 * E * INERTIA)
    assert result.displacements[2][1] == pytest.approx(euler_deflection, rel=1e-5)


def test_p_delta_compression_increases_lateral_response_and_converges():
    length, lateral_force = 3.0, -1_000.0
    p_cr = math.pi**2 * E * INERTIA / (4.0 * length**2)
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION),),
        restraints=((True, True, True), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (-0.5 * p_cr, lateral_force, 0.0)),
    )
    first_order = tm.analyze_linear_static(model)
    second_order = tm.analyze_p_delta(model)
    assert second_order.analysis_type == "p_delta"
    assert second_order.iteration_count > 1
    assert abs(second_order.displacements[1][1]) > abs(first_order.displacements[1][1])
    assert second_order.free_dof_residual_norm < 1e-5
    assert second_order.global_equilibrium_residual == pytest.approx((0.0, 0.0, 0.0), abs=1.0)


def test_simply_supported_uniform_load_reactions_match_equilibrium():
    length, load = 6.0, -4_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION, uniform_load_local_y_n_m=load),),
        restraints=((True, True, False), (False, True, False)),
    )
    result = tm.analyze_linear_static(model)
    assert result.reactions[0][1] == pytest.approx(-load * length / 2)
    assert result.reactions[1][1] == pytest.approx(-load * length / 2)
    assert result.displacements[0][1] == pytest.approx(0.0)
    assert result.displacements[1][1] == pytest.approx(0.0)
    assert result.displacements[0][2] == pytest.approx(-result.displacements[1][2])
    assert result.global_equilibrium_residual == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)


def test_uniform_axial_member_load_matches_bar_solution():
    length, load = 3.0, 2_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION, uniform_load_local_x_n_m=load),),
        restraints=((True, True, True), (False, True, True)),
    )
    result = tm.analyze_linear_static(model)
    assert result.displacements[1][0] == pytest.approx(load * length**2 / (2 * E * AREA))
    assert result.reactions[0][0] == pytest.approx(-load * length)


def test_concentrated_member_loads_and_released_ends_on_simple_support():
    length, load = 6.0, -12_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, SECTION,
            point_loads=(tm.FramePointLoad(length / 2, force_local_y_n=load),),
            release_rotation_i=True,
            release_rotation_j=True,
        ),),
        restraints=((True, True, False), (False, True, False)),
    )
    result = tm.analyze_linear_static(model)
    assert result.reactions[0][1] == pytest.approx(-load / 2)
    assert result.reactions[1][1] == pytest.approx(-load / 2)
    assert result.member_end_forces_local[0][2] == pytest.approx(0.0, abs=1e-8)
    assert result.member_end_forces_local[0][5] == pytest.approx(0.0, abs=1e-8)


def test_released_supports_have_zero_reaction_moments_and_correct_beam_deflection():
    length, force = 6.0, -12_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length / 2, 0.0), tm.FrameNode(length, 0.0)),
        members=(
            tm.FrameMember(0, 1, MATERIAL, SECTION, release_rotation_i=True),
            tm.FrameMember(1, 2, MATERIAL, SECTION, release_rotation_j=True),
        ),
        restraints=((True, True, False), (False, False, False), (False, True, False)),
        nodal_loads=((0.0, 0.0, 0.0), (0.0, force, 0.0), (0.0, 0.0, 0.0)),
    )
    result = tm.analyze_linear_static(model)
    expected_midspan_deflection = force * length**3 / (48 * E * INERTIA)
    assert result.displacements[1][1] == pytest.approx(expected_midspan_deflection)
    assert result.reactions[0][2] == pytest.approx(0.0, abs=1e-8)
    assert result.reactions[2][2] == pytest.approx(0.0, abs=1e-8)


def test_concentrated_member_moment_has_correct_support_couple():
    length, moment = 6.0, 3_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, SECTION,
            point_loads=(tm.FramePointLoad(length / 2, moment_local_z_n_m=moment),),
            release_rotation_i=True,
            release_rotation_j=True,
        ),),
        restraints=((True, True, False), (False, True, False)),
    )
    result = tm.analyze_linear_static(model)
    assert result.reactions[0][1] == pytest.approx(moment / length)
    assert result.reactions[1][1] == pytest.approx(-moment / length)
    assert result.global_equilibrium_residual == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)


def test_shear_flexible_cantilever_off_centre_point_load_matches_closed_form():
    # Timoshenko cantilever loaded at a: w(L) = P a^2 (3L - a) / (6 E I) + P a / (G A_s),
    # and the tip rotation P a^2 / (2 E I) is unchanged by shear.
    length, location, force, shear_area = 3.0, 0.75, -12_000.0, 0.0002
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, tm.FrameSection(AREA, INERTIA, shear_area),
            point_loads=(tm.FramePointLoad(location, force_local_y_n=force),),
        ),),
        restraints=((True, True, True), (False, False, False)),
    )
    result = tm.analyze_linear_static(model)
    bending = force * location**2 * (3 * length - location) / (6 * E * INERTIA)
    shear = force * location / (G * shear_area)
    assert abs(shear / bending) > 0.05
    assert result.displacements[1][1] == pytest.approx(bending + shear)
    assert result.displacements[1][2] == pytest.approx(force * location**2 / (2 * E * INERTIA))
    assert result.reactions[0] == pytest.approx((0.0, -force, -force * location))


@pytest.mark.parametrize("shear_area", [None, 0.004, 0.0005])
@pytest.mark.parametrize("point_load", [
    {"force_local_y_n": -12_000.0},
    {"moment_local_z_n_m": 3_000.0},
])
@pytest.mark.parametrize("release_j", [False, True])
def test_member_point_load_matches_model_split_at_the_load(shear_area, point_load, release_j):
    # A nodal load is exact for this element, so a member split at the load is the reference.
    length, location = 3.0, 0.75
    section = tm.FrameSection(AREA, INERTIA, shear_area)
    fixed, free = (True, True, True), (False, False, False)
    single = tm.analyze_linear_static(tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, section,
            point_loads=(tm.FramePointLoad(location, **point_load),),
            release_rotation_j=release_j,
        ),),
        restraints=(fixed, fixed),
    ))
    split = tm.analyze_linear_static(tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(location, 0.0), tm.FrameNode(length, 0.0)),
        members=(
            tm.FrameMember(0, 1, MATERIAL, section),
            tm.FrameMember(1, 2, MATERIAL, section, release_rotation_j=release_j),
        ),
        restraints=(fixed, free, fixed),
        nodal_loads=(
            (0.0, 0.0, 0.0),
            (0.0, point_load.get("force_local_y_n", 0.0), point_load.get("moment_local_z_n_m", 0.0)),
            (0.0, 0.0, 0.0),
        ),
    ))
    assert single.reactions[0] == pytest.approx(split.reactions[0], abs=1e-6)
    assert single.reactions[1] == pytest.approx(split.reactions[2], abs=1e-6)
    assert single.member_end_forces_local[0][:3] == pytest.approx(split.member_end_forces_local[0][:3], abs=1e-6)
    assert single.member_end_forces_local[0][3:] == pytest.approx(split.member_end_forces_local[1][3:], abs=1e-6)


def test_axial_bar_and_prescribed_support_displacement():
    length, force = 2.0, 5_000.0
    bar = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.AxialMember(0, 1, E, AREA),),
        restraints=((True, True, True), (False, True, False)),
        nodal_loads=((0.0, 0.0, 0.0), (force, 0.0, 0.0)),
    )
    result = tm.analyze_linear_static(bar)
    assert result.displacements[1][0] == pytest.approx(force * length / (E * AREA))
    assert result.member_end_normal_stresses_pa[0] == pytest.approx((force / AREA,) * 4)

    imposed = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.AxialMember(0, 1, E, AREA),),
        restraints=((True, True, True), (True, True, True)),
        prescribed_displacements=((0.0, 0.0, 0.0), (1e-3, 0.0, 0.0)),
    )
    imposed_result = tm.analyze_linear_static(imposed)
    assert imposed_result.displacements[1][0] == pytest.approx(1e-3)
    assert imposed_result.reactions[0][0] == pytest.approx(-E * AREA * 1e-3 / length)


def test_frame_end_stress_recovery_uses_selected_section_moduli():
    length, force = 3.0, -1_000.0
    section = tm.rectangle_section(0.2, 0.5)
    frame_section = tm.FrameSection(
        section.area_m2,
        section.second_moment_z_m4,
        section_modulus_at_positive_local_y_m3=section.section_modulus_z_m3,
        section_modulus_at_negative_local_y_m3=section.section_modulus_z_m3,
    )
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, frame_section),),
        restraints=((True, True, True), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (0.0, force, 0.0)),
    )
    result = tm.analyze_linear_static(model)
    expected_stress = abs(force) * length / section.section_modulus_z_m3
    # The free-end stresses are zero up to round-off, which differs between BLAS builds.
    assert result.member_end_normal_stresses_pa[0] == pytest.approx(
        (expected_stress, -expected_stress, 0.0, 0.0), abs=1e-9 * expected_stress
    )


def test_rotated_member_uses_global_support_and_load_axes():
    length, force = 2.0, 10_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(0.0, length)),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION),),
        restraints=((True, True, True), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (force, 0.0, 0.0)),
    )
    result = tm.analyze_linear_static(model)
    assert result.displacements[1][0] == pytest.approx(force * length**3 / (3 * E * INERTIA))
    assert result.reactions[0][0] == pytest.approx(-force)


def test_modal_axial_bar_matches_one_element_generalized_eigenvalue():
    length, mass_per_length = 3.0, 12.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION, mass_per_length_kg_m=mass_per_length),),
        restraints=((True, True, True), (False, True, True)),
    )
    result = tm.analyze_modes(model, mode_count=1)
    expected = math.sqrt(3 * E * AREA / (mass_per_length * length**2)) / (2 * math.pi)
    assert result.frequencies_hz == pytest.approx((expected,))
    assert result.mode_shapes[0][1] == pytest.approx((1.0, 0.0, 0.0))
    assert result.generalized_masses_kg == pytest.approx((mass_per_length * length / 3,))
    assert result.participation_factors_x == pytest.approx((1.0,))
    assert result.effective_modal_masses_x_kg == pytest.approx((mass_per_length * length / 3,))
    assert result.effective_modal_mass_ratios_x == pytest.approx((1.0,))


def test_modal_assurance_criterion_handles_scaling_and_complex_shapes():
    assert tm.modal_assurance_criterion([1.0, 2.0], [3.0, 6.0]) == pytest.approx(1.0)
    assert tm.modal_assurance_criterion([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert tm.modal_assurance_criterion([1j, 2j], [2.0, 4.0]) == pytest.approx(1.0)
    with pytest.raises(ValueError, match="equal length"):
        tm.modal_assurance_criterion([1.0], [1.0, 2.0])


def test_linear_buckling_column_converges_under_mesh_refinement():
    length, reference_load = 3.0, 1_000.0
    exact_critical_load = math.pi**2 * E * INERTIA / (4.0 * length**2)
    estimates = []
    for element_count in (1, 2, 4):
        nodes = tuple(tm.FrameNode(0.0, length * index / element_count) for index in range(element_count + 1))
        members = tuple(tm.FrameMember(index, index + 1, MATERIAL, SECTION) for index in range(element_count))
        model = tm.StructuralModel(
            nodes=nodes,
            members=members,
            restraints=((True, True, True),) + ((False, False, False),) * element_count,
            nodal_loads=((0.0, 0.0, 0.0),) * element_count + ((0.0, -reference_load, 0.0),),
        )
        result = tm.analyze_linear_buckling(model, mode_count=1)
        estimates.append(result.critical_load_factors[0] * reference_load)
        assert result.reference_member_axial_forces_n == pytest.approx((-reference_load,) * element_count)
    assert abs(estimates[1] - exact_critical_load) < abs(estimates[0] - exact_critical_load)
    assert estimates[-1] == pytest.approx(exact_critical_load, rel=1e-4)


def test_triangular_truss_and_portal_frame_assemble_global_equilibrium():
    truss = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(2.0, 0.0), tm.FrameNode(1.0, 1.0)),
        members=(
            tm.AxialMember(0, 1, E, AREA),
            tm.AxialMember(0, 2, E, AREA),
            tm.AxialMember(1, 2, E, AREA),
        ),
        restraints=((True, True, False), (True, True, False), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (10_000.0, 0.0, 0.0)),
    )
    truss_result = tm.analyze_linear_static(truss)
    assert truss_result.reactions[0][0] + truss_result.reactions[1][0] == pytest.approx(-10_000.0)
    assert truss_result.displacements[2][0] > 0.0
    assert truss_result.global_equilibrium_residual == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)

    nodes = (tm.FrameNode(0.0, 0.0), tm.FrameNode(4.0, 0.0), tm.FrameNode(0.0, 3.0), tm.FrameNode(4.0, 3.0))
    portal = tm.StructuralModel(
        nodes=nodes,
        members=(
            tm.FrameMember(0, 2, MATERIAL, SECTION),
            tm.FrameMember(1, 3, MATERIAL, SECTION),
            tm.FrameMember(2, 3, MATERIAL, SECTION),
        ),
        restraints=((True, True, True), (True, True, True), (False, False, False), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (5_000.0, 0.0, 0.0), (5_000.0, 0.0, 0.0)),
    )
    portal_result = tm.analyze_linear_static(portal)
    assert portal_result.reactions[0][0] + portal_result.reactions[1][0] == pytest.approx(-10_000.0)
    assert portal_result.displacements[2][0] == pytest.approx(portal_result.displacements[3][0], rel=1e-12)
    assert portal_result.global_equilibrium_residual == pytest.approx((0.0, 0.0, 0.0), abs=1e-7)


@pytest.mark.parametrize(
    "factory",
    [
        lambda: tm.FrameMaterial(0.0, G),
        lambda: tm.FrameSection(AREA, 0.0),
        lambda: tm.FrameSection(AREA, INERTIA, 0.0),
        lambda: tm.FrameMember(0, 0, MATERIAL, SECTION),
    ],
)
def test_frame_component_dimensions_are_validated(factory):
    with pytest.raises(ValueError):
        factory()


def test_frame_section_from_standard_properties_maps_axis_and_modulus():
    properties = tm.rectangle_section(0.3, 0.6)
    section_y = tm.FrameSection.from_properties(
        properties, shear_area_local_y_m2=0.012
    )
    section_z = tm.FrameSection.from_properties(properties, bending_axis="z")

    assert section_y.area_m2 == properties.area_m2
    assert section_y.second_moment_local_z_m4 == properties.second_moment_y_m4
    assert section_y.shear_area_local_y_m2 == 0.012
    assert section_y.section_modulus_at_positive_local_y_m3 == properties.section_modulus_y_m3
    assert section_y.section_modulus_at_negative_local_y_m3 == properties.section_modulus_y_m3
    assert section_z.second_moment_local_z_m4 == properties.second_moment_z_m4
    assert section_z.section_modulus_at_positive_local_y_m3 == properties.section_modulus_z_m3
    assert section_z.shear_area_local_y_m2 is None


def test_frame_section_from_principal_polygon_properties_and_rejects_coupled_axes():
    outline = [(0.0, 0.0), (0.3, 0.0), (0.3, 0.6), (0.0, 0.6)]
    properties = tm.polygon_section(outline)
    section = tm.FrameSection.from_properties(properties, bending_axis="x")

    assert section.area_m2 == properties.area_m2
    assert section.second_moment_local_z_m4 == properties.second_moment_x_m4
    assert section.section_modulus_at_positive_local_y_m3 == properties.section_modulus_x_positive_m3
    assert section.section_modulus_at_negative_local_y_m3 == properties.section_modulus_x_negative_m3

    angle = 0.4
    rotated = [
        (math.cos(angle) * x - math.sin(angle) * y,
         math.sin(angle) * x + math.cos(angle) * y)
        for x, y in outline
    ]
    coupled = tm.polygon_section(rotated)
    with pytest.raises(ValueError, match="axes must be principal"):
        tm.FrameSection.from_properties(coupled)


def test_frame_section_from_properties_validates_property_type_and_axis():
    with pytest.raises(TypeError, match="SectionProperties or PolygonSectionProperties"):
        tm.FrameSection.from_properties(object())
    with pytest.raises(ValueError, match="must be 'y' or 'z'"):
        tm.FrameSection.from_properties(tm.rectangle_section(0.3, 0.6), bending_axis="x")
    with pytest.raises(ValueError, match="must be 'x' or 'y'"):
        tm.FrameSection.from_properties(
            tm.polygon_section([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]),
            bending_axis="z",
        )


def test_frame_material_checks_optional_isotropic_constants():
    shear = E / (2 * (1 + 0.3))
    assert tm.FrameMaterial(E, shear, 0.3).poisson_ratio == pytest.approx(0.3)
    with pytest.raises(ValueError, match="inconsistent"):
        tm.FrameMaterial(E, 0.5 * shear, 0.3)
    with pytest.raises(ValueError, match="between -1 and 0.5"):
        tm.FrameMaterial(E, shear, 0.5)


def test_structural_model_rejects_invalid_indices_and_singular_supports():
    with pytest.raises(ValueError, match="node indices"):
        tm.StructuralModel(
            nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(1.0, 0.0)),
            members=(tm.FrameMember(0, 2, MATERIAL, SECTION),),
            restraints=((True, True, True), (False, False, False)),
        )
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(1.0, 0.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION),),
        restraints=((False, False, False), (False, False, False)),
    )
    with pytest.raises(ValueError, match="singular"):
        tm.analyze_linear_static(model)


def test_modal_analysis_requires_mass_on_free_degrees():
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(1.0, 0.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION),),
        restraints=((True, True, True), (False, False, False)),
    )
    with pytest.raises(ValueError, match="mass matrix"):
        tm.analyze_modes(model)


def _json_round_trip(result):
    data = result.to_dict()
    assert json.loads(json.dumps(data)) == data
    return data


def test_static_result_to_dict_round_trips_through_json():
    section = tm.FrameSection(
        AREA, INERTIA,
        section_modulus_at_positive_local_y_m3=1e-4,
        section_modulus_at_negative_local_y_m3=1e-4,
    )
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(3.0, 0.0), tm.FrameNode(3.0, 2.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, section), tm.AxialMember(1, 2, E, AREA)),
        restraints=((True, True, True), (False, False, False), (True, True, False)),
        nodal_loads=((0.0, 0.0, 0.0), (500.0, -12_000.0, 0.0), (0.0, 0.0, 0.0)),
    )
    result = tm.analyze_linear_static(model)
    data = _json_round_trip(result)
    assert data["analysis_type"] == "first_order"
    assert data["displacements"] == [list(row) for row in result.displacements]
    assert data["reactions"] == [list(row) for row in result.reactions]
    assert data["member_end_forces_local"] == [list(row) for row in result.member_end_forces_local]
    assert data["member_end_normal_stresses_pa"] == [list(row) for row in result.member_end_normal_stresses_pa]
    assert data["global_equilibrium_residual"] == list(result.global_equilibrium_residual)
    assert data["strain_energy_j"] == result.strain_energy_j


def test_static_result_to_dict_keeps_missing_member_stresses_as_none():
    data = _json_round_trip(tm.analyze_linear_static(cantilever(load_y_n=-12_000.0)))
    assert data["member_end_normal_stresses_pa"] == [None]


def test_modal_and_buckling_results_to_dict_round_trip_through_json():
    modal = tm.analyze_modes(cantilever(mass_per_length=12.0), mode_count=2)
    modal_data = _json_round_trip(modal)
    assert modal_data["frequencies_hz"] == list(modal.frequencies_hz)
    assert modal_data["mode_shapes"] == [[list(row) for row in shape] for shape in modal.mode_shapes]
    assert modal_data["notes"] == list(modal.notes)
    assert modal_data["constrained_dof_count"] == modal.constrained_dof_count

    column = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(0.0, 3.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION),),
        restraints=((True, True, True), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (0.0, -1_000.0, 0.0)),
    )
    buckling = tm.analyze_linear_buckling(column, mode_count=1)
    buckling_data = _json_round_trip(buckling)
    assert buckling_data["critical_load_factors"] == list(buckling.critical_load_factors)
    assert buckling_data["mode_shapes"] == [[list(row) for row in shape] for shape in buckling.mode_shapes]
    assert buckling_data["reference_member_axial_forces_n"] == list(buckling.reference_member_axial_forces_n)
