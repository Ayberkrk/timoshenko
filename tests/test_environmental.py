import numpy as np
import pytest

from timoshenko.environmental import fit_environmental_baseline


def test_environmental_baseline_removes_linear_temperature_shift() -> None:
    temperature = np.linspace(-10.0, 30.0, 30)
    humidity = 20.0 + 60.0 * np.linspace(0.0, 1.0, 30) ** 2
    environment = np.column_stack((temperature, humidity))
    base_frequencies = np.array([2.0, 5.0])
    slopes = np.array([[0.002, -0.001], [-0.01, 0.004]])
    centered = environment - environment.mean(axis=0)
    frequencies = base_frequencies + centered @ slopes.T

    baseline = fit_environmental_baseline(
        environment,
        frequencies,
        feature_names=("temperature_c", "humidity_pct"),
    )
    shifted = base_frequencies + np.array([0.002, -0.01]) * 8.0
    normalized = baseline.normalize(shifted, (environment.mean(axis=0) + [8.0, 0.0]))

    assert normalized == pytest.approx(tuple(base_frequencies))
    assert np.allclose(baseline.coefficients_hz_per_unit, slopes)
    assert max(baseline.residual_std_hz) < 1e-12
    assert baseline.to_dict()["sample_count"] == 30


@pytest.mark.parametrize(
    ("environment", "frequencies", "names", "message"),
    [
        ([[1.0], [2.0]], [[2.0], [2.1]], ["temperature"], "at least number_of_features"),
        ([[1.0], [1.0], [1.0]], [[2.0], [2.1], [2.2]], ["temperature"], "rank-deficient"),
        ([[1.0], [2.0], [3.0]], [[2.0], [2.1], [0.0]], ["temperature"], "finite"),
    ],
)
def test_environmental_fit_rejects_unidentifiable_or_invalid_data(
    environment, frequencies, names, message
) -> None:
    with pytest.raises(ValueError, match=message):
        fit_environmental_baseline(environment, frequencies, feature_names=names)


def test_environmental_normalization_checks_input_shape_and_positive_result() -> None:
    baseline = fit_environmental_baseline(
        [[0.0], [1.0], [2.0], [3.0]],
        [[2.0], [2.1], [2.2], [2.3]],
        feature_names=("temperature_c",),
    )
    with pytest.raises(ValueError, match="one value per fitted feature"):
        baseline.normalize((2.0,), ())
    with pytest.raises(ValueError, match="non-positive frequency"):
        baseline.normalize((1.0,), (100.0,))
