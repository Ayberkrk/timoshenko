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


@pytest.fixture
def valid_baseline():
    from timoshenko.environmental import EnvironmentalFrequencyBaseline

    return EnvironmentalFrequencyBaseline(
        feature_names=("temperature",),
        reference_environment=(20.0,),
        reference_frequencies_hz=(2.0,),
        coefficients_hz_per_unit=((0.01,),),
        residual_std_hz=(0.0,),
        sample_count=3,
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"feature_names": ()}, "distinct non-empty names"),
        ({"feature_names": (" ",)}, "distinct non-empty names"),
        ({"feature_names": ("temperature", " temperature ")}, "distinct non-empty names"),
        ({"reference_environment": ()}, "one finite value per feature"),
        ({"reference_environment": (float("nan"),)}, "one finite value per feature"),
        ({"reference_frequencies_hz": ()}, "finite positive values"),
        ({"reference_frequencies_hz": (0.0,)}, "finite positive values"),
        ({"reference_frequencies_hz": (float("inf"),)}, "finite positive values"),
        ({"coefficients_hz_per_unit": ()}, "one row per mode"),
        ({"coefficients_hz_per_unit": ((0.01, 0.02),)}, "one column per feature"),
        ({"coefficients_hz_per_unit": ((float("nan"),),)}, "coefficients must be finite"),
        ({"residual_std_hz": ()}, "one finite non-negative value per mode"),
        ({"residual_std_hz": (-0.1,)}, "one finite non-negative value per mode"),
        ({"residual_std_hz": (float("inf"),)}, "one finite non-negative value per mode"),
        ({"sample_count": 2}, "must exceed the number of features plus one"),
        ({"sample_count": True}, "must exceed the number of features plus one"),
    ],
)
def test_baseline_rejects_invalid_constructor_fields(valid_baseline, changes, message):
    from dataclasses import replace

    with pytest.raises(ValueError, match=message):
        replace(valid_baseline, **changes)


@pytest.mark.parametrize(
    ("frequencies", "environment", "message"),
    [
        ((), (20.0,), "one value per fitted mode"),
        ((2.0,), (float("nan"),), "environment values must be finite"),
        ((2.0,), (float("inf"),), "environment values must be finite"),
        ((0.0,), (20.0,), "finite positive values"),
        ((float("nan"),), (20.0,), "finite positive values"),
    ],
)
def test_normalize_rejects_invalid_measurements(valid_baseline, frequencies, environment, message):
    with pytest.raises(ValueError, match=message):
        valid_baseline.normalize(frequencies, environment)


@pytest.mark.parametrize(
    ("environment", "frequencies", "names", "message"),
    [
        ([1.0, 2.0, 3.0], [[2.0], [2.1], [2.2]], ["t"], "2D arrays"),
        ([[1.0], [2.0], [3.0]], [2.0, 2.1, 2.2], ["t"], "2D arrays"),
        ([[1.0], [2.0], [3.0]], [[2.0], [2.1]], ["t"], "same record count"),
        ([[1.0], [2.0], [3.0]], [[2.0], [2.1], [2.2]], [], "name each"),
        ([[1.0], [2.0], [3.0]], [[2.0], [2.1], [2.2]], [" "], "name each"),
        ([[1.0, 2.0]] * 4, [[2.0]] * 4, ["t", "t"], "must be distinct"),
        ([[1.0], [2.0], [3.0]], [[], [], []], ["t"], "baseline records"),
        ([[1.0], [2.0], [float("nan")]], [[2.0]] * 3, ["t"], "must be finite"),
    ],
)
def test_fit_rejects_invalid_array_shapes_and_features(environment, frequencies, names, message):
    with pytest.raises(ValueError, match=message):
        fit_environmental_baseline(environment, frequencies, feature_names=names)
