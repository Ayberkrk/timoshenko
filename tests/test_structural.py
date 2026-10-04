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


def test_recover_member_response_for_simply_supported_uniform_load():
    length, load, shear_area = 6.0, -4_000.0, 0.004
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, tm.FrameSection(AREA, INERTIA, shear_area),
            uniform_load_local_y_n_m=load,
        ),),
        restraints=((True, True, False), (False, True, False)),
    )
    result = tm.analyze_linear_static(model)
    response = tm.recover_member_response(model, result, 0, (0.0, length / 2, length))

    expected_midspan_deflection = load * length**4 / (384 * E * INERTIA) * 5
    expected_midspan_deflection += load * length**2 / (8 * G * shear_area)
    assert response.axial_forces_n == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    assert response.shear_forces_n == pytest.approx((-load * length / 2, 0.0, load * length / 2))
    assert response.bending_moments_n_m == pytest.approx(
        (0.0, -load * length**2 / 8, 0.0), abs=1e-9
    )
    assert response.transverse_deflections_m == pytest.approx(
        (0.0, expected_midspan_deflection, 0.0), abs=3e-12
    )
    assert response.maximum_absolute_moment_n_m == pytest.approx(-load * length**2 / 8)
    assert response.maximum_absolute_moment_location_m == pytest.approx(length / 2)
    assert response.maximum_moment_n_m == pytest.approx(-load * length**2 / 8)
    assert response.minimum_moment_n_m == pytest.approx(0.0, abs=3e-12)


def test_recover_member_response_finds_fixed_fixed_uniform_load_extremes():
    length, load = 6.0, -4_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(0, 1, MATERIAL, SECTION, uniform_load_local_y_n_m=load),),
        restraints=((True, True, True), (True, True, True)),
    )
    response = tm.recover_member_response(model, tm.analyze_linear_static(model), 0, (0.0, length / 2, length))

    assert response.bending_moments_n_m == pytest.approx(
        (load * length**2 / 12, -load * length**2 / 24, load * length**2 / 12)
    )
    assert response.minimum_moment_n_m == pytest.approx(load * length**2 / 12)
    assert response.maximum_moment_n_m == pytest.approx(-load * length**2 / 24)
    assert response.maximum_absolute_moment_n_m == pytest.approx(-load * length**2 / 12)
    assert response.maximum_absolute_moment_location_m == pytest.approx(0.0)


def test_recover_member_response_has_point_load_jumps_and_matches_tip_displacement():
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
    offset = 1e-8
    response = tm.recover_member_response(
        model, result, 0, (location - offset, location, location + offset, length)
    )

    assert response.shear_forces_n[1] - response.shear_forces_n[0] == pytest.approx(force)
    assert response.bending_moments_n_m[1] == pytest.approx(response.bending_moments_n_m[0], abs=1e-3)
    assert response.transverse_deflections_m[-1] == pytest.approx(result.displacements[1][1], abs=1e-12)
    assert response.maximum_absolute_moment_n_m == pytest.approx(abs(force * location))
    assert response.maximum_absolute_moment_location_m == pytest.approx(0.0)


def test_recover_member_response_axial_force_is_tension_positive_and_jumps_at_point_load():
    length, location, force = 3.0, 0.75, 12_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, SECTION,
            point_loads=(tm.FramePointLoad(location, force_local_x_n=force),),
        ),),
        restraints=((True, True, True), (False, False, False)),
    )
    response = tm.recover_member_response(
        model,
        tm.analyze_linear_static(model),
        0,
        (0.0, location - 1e-8, location, length),
    )

    assert response.axial_forces_n == pytest.approx((force, force, 0.0, 0.0))


def test_recover_member_response_accounts_for_released_end_rotation_and_point_moment_jump():
    length, location, moment = 6.0, 2.0, 3_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, SECTION,
            point_loads=(tm.FramePointLoad(location, moment_local_z_n_m=moment),),
            release_rotation_i=True,
            release_rotation_j=True,
        ),),
        restraints=((True, True, False), (False, True, False)),
    )
    result = tm.analyze_linear_static(model)
    offset = 1e-8
    response = tm.recover_member_response(
        model, result, 0, (0.0, location - offset, location, location + offset, length)
    )

    assert response.bending_moments_n_m[2] - response.bending_moments_n_m[1] == pytest.approx(-moment)
    assert response.transverse_deflections_m[0] == pytest.approx(result.displacements[0][1])
    assert response.transverse_deflections_m[-1] == pytest.approx(result.displacements[1][1])


def test_recover_member_response_validates_member_and_analysis_type():
    model = cantilever(load_y_n=-1_000.0)
    result = tm.analyze_linear_static(model)
    with pytest.raises(ValueError, match="member_index"):
        tm.recover_member_response(model, result, 1, (0.0,))
    with pytest.raises(ValueError, match="must not exceed"):
        tm.recover_member_response(model, result, 0, (3.1,))
    with pytest.raises(TypeError, match="FrameMember"):
        truss = tm.StructuralModel(
            nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(1.0, 0.0)),
            members=(tm.AxialMember(0, 1, E, AREA),),
            restraints=((True, True, True), (False, True, True)),
        )
        tm.recover_member_response(truss, tm.analyze_linear_static(truss), 0, (0.0,))
    with pytest.raises(ValueError, match="first-order"):
        p_delta = tm.analyze_p_delta(model)
        tm.recover_member_response(model, p_delta, 0, (0.0,))


@pytest.mark.parametrize("shear_area", [None, 0.004])
def test_full_span_partial_uniform_load_matches_existing_uniform_load(shear_area):
    length = 6.0
    section = tm.FrameSection(AREA, INERTIA, shear_area)
    uniform = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, section,
            uniform_load_local_x_n_m=700.0,
            uniform_load_local_y_n_m=-4_000.0,
        ),),
        restraints=((True, True, True), (False, False, False)),
    )
    partial = tm.StructuralModel(
        nodes=uniform.nodes,
        members=(tm.FrameMember(
            0, 1, MATERIAL, section,
            partial_uniform_loads=(tm.FramePartialUniformLoad(
                0.0, length, intensity_local_x_n_m=700.0, intensity_local_y_n_m=-4_000.0
            ),),
        ),),
        restraints=uniform.restraints,
    )

    uniform_result = tm.analyze_linear_static(uniform)
    partial_result = tm.analyze_linear_static(partial)
    for actual, expected in zip(partial_result.displacements, uniform_result.displacements, strict=True):
        assert actual == pytest.approx(expected, abs=1e-12)
    for actual, expected in zip(partial_result.reactions, uniform_result.reactions, strict=True):
        assert actual == pytest.approx(expected, abs=1e-9)
    for actual, expected in zip(
        partial_result.member_end_forces_local,
        uniform_result.member_end_forces_local,
        strict=True,
    ):
        assert actual == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize("shear_area", [None, 0.004])
def test_partial_uniform_load_matches_model_split_at_load_ends(shear_area):
    length, start, end, load = 6.0, 1.5, 4.0, -4_000.0
    section = tm.FrameSection(AREA, INERTIA, shear_area)
    single_model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, section,
            partial_uniform_loads=(tm.FramePartialUniformLoad(start, end, intensity_local_y_n_m=load),),
        ),),
        restraints=((True, True, True), (True, True, True)),
    )
    split_nodes = (tm.FrameNode(0.0, 0.0), tm.FrameNode(start, 0.0),
                   tm.FrameNode(end, 0.0), tm.FrameNode(length, 0.0))
    split_model = tm.StructuralModel(
        nodes=split_nodes,
        members=(
            tm.FrameMember(0, 1, MATERIAL, section),
            tm.FrameMember(1, 2, MATERIAL, section, uniform_load_local_y_n_m=load),
            tm.FrameMember(2, 3, MATERIAL, section),
        ),
        restraints=((True, True, True), (False, False, False),
                    (False, False, False), (True, True, True)),
    )
    single_result = tm.analyze_linear_static(single_model)
    split_result = tm.analyze_linear_static(split_model)
    single_response = tm.recover_member_response(single_model, single_result, 0, (start, end))

    assert single_result.reactions[0] == pytest.approx(split_result.reactions[0], abs=1e-6)
    assert single_result.reactions[1] == pytest.approx(split_result.reactions[3], abs=1e-6)
    assert single_result.member_end_forces_local[0][:3] == pytest.approx(
        split_result.member_end_forces_local[0][:3], abs=1e-6
    )
    assert single_result.member_end_forces_local[0][3:] == pytest.approx(
        split_result.member_end_forces_local[2][3:], abs=1e-6
    )
    assert single_response.transverse_deflections_m == pytest.approx(
        (split_result.displacements[1][1], split_result.displacements[2][1]), abs=1e-12
    )


def test_half_span_uniform_load_matches_fixed_fixed_end_moment_reference():
    length, load = 6.0, -4_000.0
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(length, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, SECTION,
            partial_uniform_loads=(tm.FramePartialUniformLoad(
                0.0, length / 2, intensity_local_y_n_m=load
            ),),
        ),),
        restraints=((True, True, True), (True, True, True)),
    )
    result = tm.analyze_linear_static(model)

    assert result.member_end_forces_local[0][2] == pytest.approx(-load * length**2 * 11 / 192)
    assert result.member_end_forces_local[0][5] == pytest.approx(load * length**2 * 5 / 192)


@pytest.mark.parametrize(
    "load, message",
    [
        (lambda: tm.FramePartialUniformLoad(-0.1, 1.0), "non-negative"),
        (lambda: tm.FramePartialUniformLoad(1.0, 1.0), "greater than start"),
    ],
)
def test_partial_uniform_load_validates_interval(load, message):
    with pytest.raises(ValueError, match=message):
        load()


def test_partial_uniform_load_must_fit_member_length():
    model = tm.StructuralModel(
        nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(3.0, 0.0)),
        members=(tm.FrameMember(
            0, 1, MATERIAL, SECTION,
            partial_uniform_loads=(tm.FramePartialUniformLoad(1.0, 4.0, intensity_local_y_n_m=-1_000.0),),
        ),),
        restraints=((True, True, True), (False, False, False)),
    )
    with pytest.raises(ValueError, match="must not exceed the member length"):
        tm.analyze_linear_static(model)


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
