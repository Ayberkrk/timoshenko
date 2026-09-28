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
