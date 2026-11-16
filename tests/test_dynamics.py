import math
import re

import numpy as np
import pytest

from timoshenko.dynamics import analyze_time_history
from timoshenko.structural import (
    AxialMember,
    FrameMaterial,
    FrameMember,
    FrameNode,
    FrameSection,
    StructuralModel,
)


def axial_oscillator():
    length = 2.0
    youngs_modulus = 1000.0
    mass_per_length = 3.0
    model = StructuralModel(
        nodes=(FrameNode(0.0, 0.0), FrameNode(length, 0.0)),
        members=(AxialMember(0, 1, youngs_modulus, 1.0, mass_per_length_kg_m=mass_per_length),),
        restraints=((True, True, True), (False, True, True)),
    )
    stiffness = youngs_modulus / length
    mass = mass_per_length * length / 3.0
    return model, stiffness, mass


def test_newmark_axial_step_response_matches_single_degree_of_freedom_solution():
    model, stiffness, mass = axial_oscillator()
    dt = 0.0005
    times = np.arange(2001) * dt
    loads = np.zeros((len(times), 6))
    loads[:, 3] = 1.0

    result = analyze_time_history(model, times, force_history_n=loads)

    omega = math.sqrt(stiffness / mass)
    expected = (1.0 / stiffness) * (1.0 - np.cos(omega * times[-1]))
    expected_velocity = (omega / stiffness) * np.sin(omega * times[-1])
    assert result.displacements[-1][1][0] == pytest.approx(expected, rel=1e-4)
    assert result.velocities[-1][1][0] == pytest.approx(expected_velocity, rel=1e-3)
    assert result.accelerations[0][1][0] == pytest.approx(1.0 / mass)
    assert max(result.free_dof_residual_norms) < 1e-9


def test_base_acceleration_creates_inertia_force_and_serializes():
    model, _, _ = axial_oscillator()
    times = np.linspace(0.0, 0.1, 51)
    ground = np.ones_like(times)
    result = analyze_time_history(model, times, base_acceleration_m_s2=ground, direction="x")
    assert result.displacements[1][1][0] < 0.0
    assert result.method == "newmark_average_acceleration"
    assert len(result.to_dict()["reactions"]) == len(times)


@pytest.mark.parametrize(
    "times, message",
    [
        ([0.0], "at least two"),
        ([0.0, 0.1, 0.19], "uniformly spaced"),
        ([0.0, 0.1, 0.1], "strictly increasing"),
    ],
)
def test_time_grid_validation(times, message):
    model, _, _ = axial_oscillator()
    with pytest.raises(ValueError, match=message):
        analyze_time_history(model, times)


def test_force_history_shape_and_rayleigh_parameters_are_validated():
    model, _, _ = axial_oscillator()
    times = np.asarray([0.0, 0.1])
    with pytest.raises(ValueError, match="force_history_n"):
        analyze_time_history(model, times, force_history_n=np.zeros((2, 5)))
    with pytest.raises(ValueError, match="rayleigh_mass_per_s"):
        analyze_time_history(model, times, rayleigh_mass_per_s=-1.0)


@pytest.mark.parametrize(
    ("parameter", "message"),
    (
        ("initial_displacements_m", "initial displacements"),
        ("initial_velocities_m_s", "initial velocities"),
    ),
)
def test_initial_conditions_on_restrained_dofs_are_rejected(parameter, message):
    model, _, _ = axial_oscillator()
    options = {parameter: np.asarray([1.0, 0.0, 0.0, 0.0, 0.0, 0.0])}
    with pytest.raises(ValueError, match=message):
        analyze_time_history(model, [0.0, 0.1], **options)


def test_rejects_model_that_is_not_a_structural_model():
    with pytest.raises(TypeError, match="model must be a StructuralModel or StructuralModel3D"):
        analyze_time_history("not a model", [0.0, 0.1])


@pytest.mark.parametrize("stiffness_damping", [-1.0, float("nan"), float("inf")])
def test_rejects_negative_or_non_finite_rayleigh_stiffness(stiffness_damping):
    model, _, _ = axial_oscillator()
    with pytest.raises(ValueError, match="rayleigh_stiffness_s must be finite and non-negative"):
        analyze_time_history(
            model,
            [0.0, 0.1],
            rayleigh_mass_per_s=0.0,
            rayleigh_stiffness_s=stiffness_damping,
        )


@pytest.mark.parametrize("direction", ["z", "theta"])
def test_rejects_invalid_direction_with_base_acceleration(direction):
    model, _, _ = axial_oscillator()
    # re.escape stops pytest from reading the square brackets in the message as a regex.
    message = re.escape("direction must be one of ['x', 'y']")
    with pytest.raises(ValueError, match=message):
        analyze_time_history(
            model, [0.0, 0.1], base_acceleration_m_s2=[0.0, 0.0], direction=direction
        )


@pytest.mark.parametrize(
    "ground",
    [
        [0.0],
        [0.0, 0.0, 0.0],
        [0.0, float("nan")],
        [0.0, float("inf")],
    ],
)
def test_rejects_base_acceleration_with_wrong_length_or_non_finite_values(ground):
    model, _, _ = axial_oscillator()
    with pytest.raises(
        ValueError, match="base_acceleration_m_s2 must have one finite value per time step"
    ):
        analyze_time_history(model, [0.0, 0.1], base_acceleration_m_s2=ground, direction="x")


@pytest.mark.parametrize("direction", ["z", "theta"])
def test_rejects_invalid_direction_without_base_acceleration(direction):
    model, _, _ = axial_oscillator()
    with pytest.raises(
        ValueError, match="direction must name a translational axis supported by the model"
    ):
        analyze_time_history(model, [0.0, 0.1], direction=direction)


def cantilever(*, release_tip_rotation):
    # One 1 m frame member, fixed at node 0. EI = 3 N*m^2, mass 1 kg/m.
    member = FrameMember(
        0,
        1,
        FrameMaterial(youngs_modulus_pa=3.0, shear_modulus_pa=1.0),
        FrameSection(area_m2=1.0, second_moment_local_z_m4=1.0),
        mass_per_length_kg_m=1.0,
        release_rotation_j=release_tip_rotation,
    )
    return StructuralModel(
        nodes=(FrameNode(0.0, 0.0), FrameNode(1.0, 0.0)),
        members=(member,),
        restraints=((True, True, True), (False, False, False)),
    )


def test_released_member_end_matches_unreleased_cantilever_and_static_deflection():
    # A rotation release at the free tip of a cantilever changes nothing physically:
    # the member end still rotates freely. The solver stores that rotation on an
    # extra internal DOF, so loads must be padded with a zero column for it.
    released = cantilever(release_tip_rotation=True)
    reference = cantilever(release_tip_rotation=False)
    times = np.linspace(0.0, 20.0, 2001)
    loads = np.zeros((len(times), 6))
    loads[:, 4] = 1.0  # constant 1 N tip force in +y (node 1, DOF uy)
    options = {"force_history_n": loads, "rayleigh_mass_per_s": 2.0}

    result = analyze_time_history(released, times, **options)
    expected = analyze_time_history(reference, times, **options)

    displacements = np.asarray(result.displacements)
    assert displacements.shape == (len(times), 2, 3)
    # Tip translations (ux, uy) match the unreleased model at every time step.
    np.testing.assert_allclose(
        displacements[:, 1, :2],
        np.asarray(expected.displacements)[:, 1, :2],
        rtol=1e-9,
        atol=1e-12,
    )
    # Damping lets the step response settle to the static cantilever deflection.
    assert displacements[-1, 1, 1] == pytest.approx(1.0 / (3.0 * 3.0), rel=1e-6)


@pytest.mark.parametrize("parameter", ["initial_displacements_m", "initial_velocities_m_s"])
@pytest.mark.parametrize(
    "values",
    [
        [0.0, 0.0, 0.0, 0.0, 0.0],  # 5 values instead of 6
        [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]],  # 2D shape (1, 6)
        [0.0, 0.0, 0.0, float("nan"), 0.0, 0.0],
        [0.0, 0.0, 0.0, float("inf"), 0.0, 0.0],
    ],
)
def test_rejects_initial_conditions_with_wrong_shape_or_non_finite_values(parameter, values):
    model, _, _ = axial_oscillator()
    # re.escape stops pytest from reading "(6,)" in the message as a regex group.
    message = re.escape(f"{parameter} must have shape (6,)")
    with pytest.raises(ValueError, match=message):
        analyze_time_history(model, [0.0, 0.1], **{parameter: values})


def test_initial_displacement_and_velocity_start_the_free_vibration():
    model, stiffness, mass = axial_oscillator()
    initial_displacement = 0.01
    initial_velocity = 0.2
    dt = 0.0005
    times = np.arange(2001) * dt

    result = analyze_time_history(
        model,
        times,
        initial_displacements_m=[0.0, 0.0, 0.0, initial_displacement, 0.0, 0.0],
        initial_velocities_m_s=[0.0, 0.0, 0.0, initial_velocity, 0.0, 0.0],
    )

    # Node 1, component ux (index 0) is the only free degree of freedom.
    assert result.displacements[0][1][0] == initial_displacement
    assert result.velocities[0][1][0] == initial_velocity
    # With no load and no damping, m*a0 + k*u0 = 0.
    assert result.accelerations[0][1][0] == pytest.approx(-stiffness * initial_displacement / mass)
    # Undamped free vibration: u(t) = u0*cos(wt) + (v0/w)*sin(wt).
    omega = math.sqrt(stiffness / mass)
    expected = initial_displacement * math.cos(omega * times[-1]) + (
        initial_velocity / omega
    ) * math.sin(omega * times[-1])
    assert result.displacements[-1][1][0] == pytest.approx(expected, rel=1e-4)


def test_massless_mechanism_makes_effective_stiffness_singular():
    # Horizontal bar: its uy row in K and M is exactly zero (sin = 0), so the
    # singularity is exact on every platform; a tilted bar would only be near-singular.
    model = StructuralModel(
        nodes=(FrameNode(0.0, 0.0), FrameNode(2.0, 0.0)),
        members=(AxialMember(0, 1, 1000.0, 1.0),),  # no mass_per_length_kg_m -> zero mass
        restraints=((True, True, True), (False, False, True)),  # node 1 uy is free
    )
    with pytest.raises(
        ValueError, match="effective dynamic stiffness is singular; check restraints and model"
    ) as excinfo:
        analyze_time_history(model, [0.0, 0.1])
    assert isinstance(excinfo.value.__cause__, np.linalg.LinAlgError)
