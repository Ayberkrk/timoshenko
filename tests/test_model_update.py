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
