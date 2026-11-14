import pytest

from timoshenko.model_update import update_story_stiffness
from timoshenko.structure import Structure


def test_story_update_recovers_local_stiffness_changes_from_complete_mode_set() -> None:
    reference = Structure(
        structure_id="three-story",
        story_masses_kg=(120_000.0, 110_000.0, 100_000.0),
        story_stiffness_n_m=(85e6, 70e6, 55e6),
    )
    changed = Structure(
        structure_id="three-story",
        story_masses_kg=reference.story_masses_kg,
        story_stiffness_n_m=(68e6, 70e6, 44e6),
    )

    result = update_story_stiffness(reference, changed.natural_frequencies_hz)

    assert result.converged
    assert result.story_stiffness_scale_factors == pytest.approx((0.8, 1.0, 0.8), abs=2e-4)
    assert result.updated_structure.story_stiffness_n_m == pytest.approx(
        changed.story_stiffness_n_m, rel=2e-4
    )
    assert result.residual_rms_pct < 0.01
    assert result.to_dict()["converged"] is True


def test_story_update_rejects_incomplete_or_invalid_modal_data() -> None:
    model = Structure(story_masses_kg=(1000.0, 800.0), story_stiffness_n_m=(1e6, 0.8e6))
    with pytest.raises(ValueError, match="one value per story mode"):
        update_story_stiffness(model, (2.0,))
    with pytest.raises(ValueError, match="finite and positive"):
        update_story_stiffness(model, (2.0, float("nan")))
    with pytest.raises(ValueError, match="ascending modal order"):
        update_story_stiffness(model, tuple(reversed(model.natural_frequencies_hz)))
    with pytest.raises(ValueError, match="regularization"):
        update_story_stiffness(model, model.natural_frequencies_hz, regularization=0.0)


def test_story_update_reports_non_convergence_at_iteration_limit() -> None:
    model = Structure(story_masses_kg=(1000.0, 800.0), story_stiffness_n_m=(1e6, 0.8e6))
    changed = Structure(story_masses_kg=model.story_masses_kg, story_stiffness_n_m=(0.4e6, 1.4e6))
    result = update_story_stiffness(model, changed.natural_frequencies_hz, maximum_iterations=1)
    assert result.iterations <= 1
    assert result.updated_structure.update_status in {
        "updated_local",
        "updated_local_not_converged",
    }


@pytest.fixture
def one_story_model():
    return Structure(story_masses_kg=(1000.0,), story_stiffness_n_m=(1e6,))


def test_story_update_rejects_non_structure():
    with pytest.raises(TypeError, match="structure must be a timoshenko.Structure"):
        update_story_stiffness(object(), (2.0,))


@pytest.mark.parametrize("maximum_iterations", [True, 0, -1, 1.5])
def test_story_update_rejects_invalid_iteration_limit(one_story_model, maximum_iterations):
    with pytest.raises(ValueError, match="maximum_iterations must be a positive integer"):
        update_story_stiffness(
            one_story_model,
            one_story_model.natural_frequencies_hz,
            maximum_iterations=maximum_iterations,
        )


@pytest.mark.parametrize("tolerance", [0.0, -1.0, float("nan"), float("inf")])
def test_story_update_rejects_invalid_tolerance(one_story_model, tolerance):
    with pytest.raises(ValueError, match="tolerance must be finite and positive"):
        update_story_stiffness(
            one_story_model, one_story_model.natural_frequencies_hz, tolerance=tolerance
        )


def test_story_update_retries_singular_solve_with_increased_damping(one_story_model, monkeypatch):
    import numpy as np

    solve = np.linalg.solve
    systems = []

    def fail_once(matrix, rhs):
        systems.append((matrix.copy(), rhs.copy()))
        if len(systems) == 1:
            raise np.linalg.LinAlgError("synthetic singular system")
        return solve(matrix, rhs)

    monkeypatch.setattr(np.linalg, "solve", fail_once)
    measured = (one_story_model.natural_frequencies_hz[0] * 0.8,)
    result = update_story_stiffness(one_story_model, measured)

    assert len(systems) > 1
    # The failed step must not change the iterate or gradient. Only damping rises.
    np.testing.assert_allclose(systems[1][1], systems[0][1], rtol=0, atol=0)
    np.testing.assert_allclose(systems[1][0] - systems[0][0], [[0.009]], atol=1e-12)
    assert result.converged
    assert result.story_stiffness_scale_factors == pytest.approx((0.64,), abs=1e-5)
    assert result.residual_rms_pct < 0.001


@pytest.mark.parametrize("failure", ["singular", "rejected"])
def test_story_update_stops_when_damping_limit_is_exceeded(one_story_model, monkeypatch, failure):
    import numpy as np

    systems = []

    def unsuccessful_solve(matrix, rhs):
        systems.append(matrix.copy())
        if failure == "singular":
            raise np.linalg.LinAlgError("synthetic persistent singularity")
        # An unchanged iterate cannot strictly improve the residual.
        return np.zeros_like(rhs)

    monkeypatch.setattr(np.linalg, "solve", unsuccessful_solve)
    measured = (one_story_model.natural_frequencies_hz[0] * 0.8,)
    result = update_story_stiffness(one_story_model, measured, maximum_iterations=100)

    assert len(systems) == result.iterations == 16
    assert all(
        later[0, 0] > earlier[0, 0] for earlier, later in zip(systems, systems[1:], strict=False)
    )
    assert not result.converged
    assert result.updated_structure.update_status == "updated_local_not_converged"
    assert result.story_stiffness_scale_factors == (1.0,)
    assert result.updated_structure.story_stiffness_n_m == one_story_model.story_stiffness_n_m
    assert result.fitted_frequencies_hz == one_story_model.natural_frequencies_hz
    assert result.residual_rms_pct == pytest.approx(25.0)
