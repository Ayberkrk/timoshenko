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


@pytest.mark.parametrize(
    "beam_scale, stiffness_factor, tolerance",
    [(1e6, 24.0, 2e-3), (1e-6, 6.0, 2e-3)],
)
def test_modal_condenses_massless_rotations_in_portal_frame(
    beam_scale, stiffness_factor, tolerance
):
    height, bay_width, lumped_mass = 3.0, 4.0, 1_000.0
    beam_section = tm.FrameSection(AREA * beam_scale, INERTIA * beam_scale)
    model = tm.StructuralModel(
        nodes=(
            tm.FrameNode(0.0, 0.0),
            tm.FrameNode(0.0, height),
            tm.FrameNode(bay_width, height),
            tm.FrameNode(bay_width, 0.0),
        ),
        members=(
            tm.FrameMember(0, 1, MATERIAL, SECTION),
            tm.FrameMember(1, 2, MATERIAL, beam_section),
            tm.FrameMember(2, 3, MATERIAL, SECTION),
        ),
        restraints=(
            (True, True, True),
            (False, False, False),
            (False, False, False),
            (True, True, True),
        ),
        nodal_lumped_masses_kg=(0.0, lumped_mass, lumped_mass, 0.0),
    )
    result = tm.analyze_modes(model, mode_count=1)
    expected_stiffness = stiffness_factor * E * INERTIA / height**3
    expected_frequency = math.sqrt(
        expected_stiffness / (2.0 * lumped_mass)
    ) / (2.0 * math.pi)
    assert result.frequencies_hz[0] == pytest.approx(expected_frequency, rel=tolerance)
    assert result.condensed_dof_count == 2
    if beam_scale < 1.0:
        assert max(abs(node[2]) for node in result.mode_shapes[0][1:3]) > 1e-2


def test_lumped_mass_two_storey_frame_matches_shear_building_limit():
    height, bay_width, mass_per_floor, rigid_factor = 3.0, 4.0, 2_000.0, 1e6
    column_stiffness = 24.0 * E * INERTIA / height**3
    beam_section = tm.FrameSection(AREA * rigid_factor, INERTIA * rigid_factor)
    model = tm.StructuralModel(
        nodes=(
            tm.FrameNode(0.0, 0.0),
            tm.FrameNode(0.0, height),
            tm.FrameNode(bay_width, height),
            tm.FrameNode(0.0, 2.0 * height),
            tm.FrameNode(bay_width, 2.0 * height),
            tm.FrameNode(bay_width, 0.0),
        ),
        members=(
            tm.FrameMember(0, 1, MATERIAL, SECTION),
            tm.FrameMember(1, 3, MATERIAL, SECTION),
            tm.FrameMember(5, 2, MATERIAL, SECTION),
            tm.FrameMember(2, 4, MATERIAL, SECTION),
            tm.FrameMember(1, 2, MATERIAL, beam_section),
            tm.FrameMember(3, 4, MATERIAL, beam_section),
        ),
        restraints=(
            (True, True, True),
            (False, True, False),
            (False, True, False),
            (False, True, False),
            (False, True, False),
            (True, True, True),
        ),
        nodal_lumped_masses_kg=(
            0.0,
            mass_per_floor / 2.0,
            mass_per_floor / 2.0,
            mass_per_floor / 2.0,
            mass_per_floor / 2.0,
            0.0,
        ),
    )
    result = tm.analyze_modes(model, mode_count=2)
    reference = tm.Structure(
        story_masses_kg=(mass_per_floor, mass_per_floor),
        story_stiffness_n_m=(column_stiffness, column_stiffness),
    )
    assert result.frequencies_hz == pytest.approx(
        reference.natural_frequencies_hz, rel=2e-3
    )
    assert result.condensed_dof_count == 4


def test_modal_zero_mass_condensation_rejects_a_free_mechanism():
    model = tm.StructuralModel(
        nodes=(
            tm.FrameNode(0.0, 0.0),
            tm.FrameNode(0.0, 3.0),
            tm.FrameNode(10.0, 0.0),
        ),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION),),
        restraints=(
            (True, True, True),
            (False, False, False),
            (False, True, True),
        ),
        nodal_lumped_masses_kg=(0.0, 1_000.0, 0.0),
    )
    with pytest.raises(
        ValueError, match="cannot be statically condensed; check for mechanisms"
    ):
        tm.analyze_modes(model)


def test_member_end_release_matches_pinned_support_in_modal_buckling_and_p_delta():
    # A release at a member end on a fully fixed node is the same structure as a pinned node.
    length, count = 3.0, 4
    nodes = tuple(tm.FrameNode(0.0, index * length / count) for index in range(count + 1))
    free = (False, False, False)

    def column(released):
        members = tuple(
            tm.FrameMember(
                index, index + 1, MATERIAL, SECTION,
                mass_per_length_kg_m=78.5,
                release_rotation_i=released and index == 0,
            )
            for index in range(count)
        )
        base = (True, True, True) if released else (True, True, False)
        return tm.StructuralModel(
            nodes=nodes,
            members=members,
            restraints=(base, *(free,) * (count - 1), (False, False, True)),
            nodal_loads=(*((0.0, 0.0, 0.0),) * count, (1_000.0, -50_000.0, 0.0)),
        )

    released, pinned = column(True), column(False)
    assert tm.analyze_modes(released, mode_count=3).frequencies_hz == pytest.approx(
        tm.analyze_modes(pinned, mode_count=3).frequencies_hz, rel=1e-9
    )
    assert tm.analyze_linear_buckling(released, mode_count=2).critical_load_factors == pytest.approx(
        tm.analyze_linear_buckling(pinned, mode_count=2).critical_load_factors, rel=1e-9
    )
    second_order = tm.analyze_p_delta(released)
    assert second_order.displacements[-1][0] == pytest.approx(
        tm.analyze_p_delta(pinned).displacements[-1][0], rel=1e-9
    )
    assert second_order.member_end_forces_local[0][2] == pytest.approx(0.0, abs=1e-6)


def test_lumped_mass_on_internal_hinge_condenses_released_rotations():
    # Two cantilevers of length a joined by a hinge carry the mass with stiffness 2 * 3 E I / a^3.
    arm, lumped_mass = 3.0, 50.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(arm, 0.0), tm.FrameNode(2.0 * arm, 0.0)),
        members=(
            tm.FrameMember(0, 1, MATERIAL, SECTION, release_rotation_j=True),
            tm.FrameMember(1, 2, MATERIAL, SECTION),
        ),
        restraints=((True, True, True), (True, False, False), (True, True, True)),
        nodal_lumped_masses_kg=(0.0, lumped_mass, 0.0),
    )
    result = tm.analyze_modes(model, mode_count=1)
    expected = math.sqrt(6.0 * E * INERTIA / arm**3 / lumped_mass) / (2.0 * math.pi)
    assert result.frequencies_hz[0] == pytest.approx(expected)
    assert result.condensed_dof_count == 2


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


def released_column(
    element_count,
    *,
    fixed_base,
    fixed_top,
    compression_n,
    lateral_n=0.0,
    top_lateral_fixed=True,
):
    length = 3.0
    nodes = tuple(
        tm.FrameNode(0.0, length * index / element_count)
        for index in range(element_count + 1)
    )
    members = tuple(
        tm.FrameMember(
            index,
            index + 1,
            MATERIAL,
            SECTION,
            release_rotation_i=index == 0 and not fixed_base,
            release_rotation_j=index == element_count - 1 and not fixed_top,
        )
        for index in range(element_count)
    )
    restraints = (
        (True, True, fixed_base),
        *((False, False, False),) * (element_count - 1),
        (top_lateral_fixed, False, fixed_top),
    )
    nodal_loads = ((0.0, 0.0, 0.0),) * element_count + (
        (lateral_n, -compression_n, 0.0),
    )
    return tm.StructuralModel(
        nodes=nodes,
        members=members,
        restraints=restraints,
        nodal_loads=nodal_loads,
    )


@pytest.mark.parametrize(
    ("fixed_base", "fixed_top", "effective_length_factor", "relative_tolerance"),
    [(False, False, 1.0, 1e-3), (True, False, 0.699, 0.02)],
)
def test_released_column_buckling_matches_euler_load_under_mesh_refinement(
    fixed_base, fixed_top, effective_length_factor, relative_tolerance
):
    reference_load = 1_000.0
    exact_critical_load = math.pi**2 * E * INERTIA / (
        effective_length_factor * 3.0
    ) ** 2
    estimates = []
    for element_count in (2, 4, 8, 16):
        model = released_column(
            element_count,
            fixed_base=fixed_base,
            fixed_top=fixed_top,
            compression_n=reference_load,
        )
        result = tm.analyze_linear_buckling(model, mode_count=1)
        estimates.append(result.critical_load_factors[0] * reference_load)
    assert abs(estimates[-1] - exact_critical_load) < abs(estimates[0] - exact_critical_load)
    assert estimates[-1] == pytest.approx(exact_critical_load, rel=relative_tolerance)


def test_pinned_pinned_modal_beam_matches_continuum_frequency():
    length, mass_per_length, element_count = 6.0, 12.0, 20
    nodes = tuple(
        tm.FrameNode(length * index / element_count, 0.0)
        for index in range(element_count + 1)
    )
    members = tuple(
        tm.FrameMember(
            index,
            index + 1,
            MATERIAL,
            SECTION,
            mass_per_length_kg_m=mass_per_length,
            release_rotation_i=index == 0,
            release_rotation_j=index == element_count - 1,
        )
        for index in range(element_count)
    )
    restraints = tuple(
        (True, True, False)
        if index in (0, element_count)
        else (True, False, False)
        for index in range(element_count + 1)
    )
    result = tm.analyze_modes(
        tm.StructuralModel(nodes=nodes, members=members, restraints=restraints),
        mode_count=1,
    )
    expected = math.pi**2 / (2.0 * math.pi * length**2) * math.sqrt(
        E * INERTIA / mass_per_length
    )
    assert result.frequencies_hz[0] == pytest.approx(expected, rel=2e-3)


def test_p_delta_accepts_pinned_base_and_matches_buckling_amplification():
    theoretical_p_cr = math.pi**2 * E * INERTIA / (0.699 * 3.0) ** 2
    compression = 0.1 * theoretical_p_cr
    lateral = 100.0
    model = released_column(
        1,
        fixed_base=False,
        fixed_top=True,
        compression_n=compression,
        lateral_n=lateral,
        top_lateral_fixed=False,
    )
    first_order = tm.analyze_linear_static(model)
    second_order = tm.analyze_p_delta(model)
    buckling = tm.analyze_linear_buckling(model, mode_count=1)
    p_cr = buckling.critical_load_factors[0] * compression
    amplification = second_order.displacements[1][0] / first_order.displacements[1][0]
    assert second_order.analysis_type == "p_delta"
    assert amplification == pytest.approx(1.0 / (1.0 - compression / p_cr), rel=1e-2)


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
        properties, bending_axis="y", shear_area_local_y_m2=0.012
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
        tm.FrameSection.from_properties(coupled, bending_axis="x")


def test_frame_section_from_tee_polygon_keeps_edge_moduli_and_end_stresses():
    # Tee symmetric about the y axis: flange 0.4 x 0.1 on top of a 0.1 x 0.5 web.
    outline = [(-0.05, 0.0), (0.05, 0.0), (0.05, 0.5), (0.2, 0.5), (0.2, 0.6), (-0.2, 0.6), (-0.2, 0.5), (-0.05, 0.5)]
    properties = tm.polygon_section(outline)
    section = tm.FrameSection.from_properties(properties, bending_axis="x")
    area = 0.4 * 0.1 + 0.1 * 0.5
    centroid = (0.4 * 0.1 * 0.55 + 0.1 * 0.5 * 0.25) / area
    inertia = (0.4 * 0.1**3 / 12 + 0.4 * 0.1 * (0.55 - centroid) ** 2
               + 0.1 * 0.5**3 / 12 + 0.1 * 0.5 * (0.25 - centroid) ** 2)
    assert section.area_m2 == pytest.approx(area)
    assert section.second_moment_local_z_m4 == pytest.approx(inertia)
    assert section.section_modulus_at_positive_local_y_m3 == pytest.approx(inertia / (0.6 - centroid))
    assert section.section_modulus_at_negative_local_y_m3 == pytest.approx(inertia / centroid)

    # Cantilever with a downward tip load: tension at the top (flange) edge of the fixed end.
    length, force = 3.0, -12_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, section),),
        restraints=((True, True, True), (False, False, False)),
        nodal_loads=((0.0, 0.0, 0.0), (0.0, force, 0.0)),
    )
    top, bottom, _, _ = tm.analyze_linear_static(model).member_end_normal_stresses_pa[0]
    moment = -force * length
    assert top == pytest.approx(moment * (0.6 - centroid) / inertia)
    assert bottom == pytest.approx(-moment * centroid / inertia)


def test_frame_section_from_properties_validates_property_type_and_axis():
    with pytest.raises(TypeError, match="SectionProperties or PolygonSectionProperties"):
        tm.FrameSection.from_properties(object(), bending_axis="y")
    with pytest.raises(TypeError):
        tm.FrameSection.from_properties(tm.rectangle_section(0.3, 0.6))
    with pytest.raises(ValueError, match="must be 'y' or 'z'"):
        tm.FrameSection.from_properties(tm.rectangle_section(0.3, 0.6), bending_axis="x")
    with pytest.raises(ValueError, match="must be 'x' or 'y'"):
        tm.FrameSection.from_properties(
            tm.polygon_section([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]),
            bending_axis="z",
        )


def test_frame_component_validation_uses_shared_error_messages():
    with pytest.raises(ValueError, match="area_m2 must be finite and greater than zero"):
        tm.FrameSection(math.inf, INERTIA)
    with pytest.raises(ValueError, match="x_m must be finite"):
        tm.FrameNode(math.nan, 0.0)


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
    assert modal_data["condensed_dof_count"] == modal.condensed_dof_count

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
