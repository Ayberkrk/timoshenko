import math

import numpy as np
import pytest

from timoshenko.dynamics import analyze_time_history
from timoshenko.structural_3d import (
    FrameMaterial3D,
    FrameMember3D,
    FrameNode3D,
    FrameSection3D,
    StructuralModel3D,
    TrussMember3D,
    analyze_linear_buckling_3d,
    analyze_linear_static_3d,
    analyze_modes_3d,
    assemble_matrices_3d,
)


def cantilever_3d(*, mass_per_length=0.0, load=0.0):
    material = FrameMaterial3D(200e9, 77e9)
    section = FrameSection3D(0.01, 8e-6, 8e-6, 1e-5)
    member = FrameMember3D(0, 1, material, section, mass_per_length_kg_m=mass_per_length)
    return StructuralModel3D(
        nodes=(FrameNode3D(0.0, 0.0, 0.0), FrameNode3D(3.0, 0.0, 0.0)),
        members=(member,),
        restraints=((True,) * 6, (False,) * 6),
        nodal_loads=((0.0,) * 6, (0.0, load, 0.0, 0.0, 0.0, 0.0)),
    )


def test_3d_cantilever_static_matches_euler_bernoulli_solution():
    force, length, young, inertia = -12_000.0, 3.0, 200e9, 8e-6
    result = analyze_linear_static_3d(cantilever_3d(load=force))
    assert result.displacements[1][1] == pytest.approx(force * length**3 / (3 * young * inertia))
    assert result.reactions[0][1] == pytest.approx(-force)
    assert result.free_dof_residual_norm < 1e-7


def test_3d_modes_condense_zero_mass_rotations_and_report_frequencies():
    model = cantilever_3d(mass_per_length=12.0)
    result = analyze_modes_3d(model, mode_count=3)
    assert len(result.frequencies_hz) == 3
    assert all(frequency > 0.0 for frequency in result.frequencies_hz)
    assert result.mode_shapes[0][1][1] != 0.0
    assert all(math.isfinite(mass) and mass > 0.0 for mass in result.generalized_masses_kg)


def test_3d_time_history_supports_massless_rotations_and_z_base_acceleration():
    model = cantilever_3d(mass_per_length=12.0)
    times = np.linspace(0.0, 0.2, 41)
    result = analyze_time_history(
        model, times, base_acceleration_m_s2=np.ones_like(times), direction="z"
    )
    assert len(result.displacements[0][0]) == 6
    assert result.displacements[-1][1][2] < 0.0
    assert max(result.free_dof_residual_norms) < 1e-5


def test_3d_truss_static_supports_arbitrary_axis():
    nodes = (FrameNode3D(0, 0, 0), FrameNode3D(1, 1, 1))
    model = StructuralModel3D(
        nodes=nodes,
        members=(TrussMember3D(0, 1, 1000.0, 1.0),),
        restraints=((True,) * 6, (False, True, True, True, True, True)),
        nodal_loads=((0.0,) * 6, (1.0, 0.0, 0.0, 0.0, 0.0, 0.0)),
    )
    result = analyze_linear_static_3d(model)
    expected_extension = 3.0 / 1000.0
    projected = sum(result.displacements[1][i] / math.sqrt(3.0) for i in range(3))
    assert projected == pytest.approx(expected_extension)


def test_3d_member_orientation_and_model_validation():
    with pytest.raises(ValueError, match="parallel"):
        model = StructuralModel3D(
            nodes=(FrameNode3D(0, 0, 0), FrameNode3D(1, 0, 0)),
            members=(
                FrameMember3D(
                    0,
                    1,
                    FrameMaterial3D(10, 5),
                    FrameSection3D(1, 1, 1, 1),
                    local_y_reference=(1, 0, 0),
                ),
            ),
            restraints=((True,) * 6, (True,) * 6),
        )
        assemble_matrices_3d(model)
    with pytest.raises(ValueError, match="six-boolean"):
        StructuralModel3D(
            nodes=(FrameNode3D(0, 0, 0), FrameNode3D(1, 0, 0)),
            members=(TrussMember3D(0, 1, 10.0, 1.0),),
            restraints=((True, True, True),),
        )


def test_3d_buckling_requires_a_compressive_reference_load_pattern():
    model = cantilever_3d(load=-1000.0)
    with pytest.raises(ValueError, match="no positive buckling factor"):
        analyze_linear_buckling_3d(model)


def test_3d_two_element_column_has_a_positive_euler_buckling_factor():
    material = FrameMaterial3D(1000.0, 500.0)
    section = FrameSection3D(1.0, 1.0, 1.0, 0.5)
    model = StructuralModel3D(
        nodes=(FrameNode3D(0, 0, 0), FrameNode3D(0, 0, 1), FrameNode3D(0, 0, 2)),
        members=(
            FrameMember3D(0, 1, material, section, local_y_reference=(0, 1, 0)),
            FrameMember3D(1, 2, material, section, local_y_reference=(0, 1, 0)),
        ),
        restraints=(
            (True, True, True, False, False, True),
            (False, False, False, False, False, True),
            (True, True, False, False, False, True),
        ),
        nodal_loads=((0,) * 6, (0,) * 6, (0, 0, -1, 0, 0, 0)),
    )
    result = analyze_linear_buckling_3d(model)
    expected = math.pi**2 * 1000.0 / 4.0
    assert result.reference_member_axial_forces_n == pytest.approx((-1.0, -1.0))
    assert result.critical_load_factors[0] == pytest.approx(expected, rel=0.01)
