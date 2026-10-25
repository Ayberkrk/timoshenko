import math

import numpy as np
import pytest

from timoshenko.dynamics import analyze_time_history
from timoshenko.structural import AxialMember, FrameNode, StructuralModel


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
