import math
from statistics import NormalDist

import pytest

import timoshenko as tm
from timoshenko.uncertainty import UncertaintyError


def test_first_order_is_exact_for_linear_function():
    result = tm.propagate_uncertainty(
        lambda a, b: 2.0 * a - 3.0 * b,
        {"a": 10.0, "b": 4.0},
        standard_uncertainties={"a": 0.2, "b": 0.1},
    )
    expected = math.sqrt((2 * 0.2) ** 2 + (3 * 0.1) ** 2)
    assert result.estimate == pytest.approx(8.0)
    assert result.standard_uncertainty == pytest.approx(expected, rel=1e-8)
    assert result.sensitivity_coefficients == pytest.approx({"a": 2.0, "b": -3.0})
    half_width = NormalDist().inv_cdf(0.975) * expected
    assert (result.interval_low, result.interval_high) == pytest.approx((8.0 - half_width, 8.0 + half_width))


def test_first_order_correlated_product_matches_gum_law():
    a, b, ua, ub, rho = 3.0, 5.0, 0.1, 0.2, 0.6
    covariance = [[ua**2, rho * ua * ub], [rho * ua * ub, ub**2]]
    result = tm.propagate_uncertainty(lambda a, b: a * b, {"a": a, "b": b}, covariance=covariance)
    variance = (b * ua) ** 2 + (a * ub) ** 2 + 2 * a * b * rho * ua * ub
    assert result.standard_uncertainty == pytest.approx(math.sqrt(variance), rel=1e-7)


def test_first_order_on_engine_equation_matches_analytic_derivatives():
    m, k, um, uk = 250.0, 4.0e5, 5.0, 8.0e3
    result = tm.propagate_uncertainty(
        tm.natural_frequency_hz,
        {"mass_kg": m, "stiffness_n_m": k},
        standard_uncertainties={"mass_kg": um, "stiffness_n_m": uk},
    )
    f = tm.natural_frequency_hz(m, k)
    expected = f * math.sqrt((0.5 * um / m) ** 2 + (0.5 * uk / k) ** 2)
    assert result.standard_uncertainty == pytest.approx(expected, rel=1e-6)


def test_monte_carlo_linear_function_matches_normal_result_and_is_seeded():
    kwargs = dict(standard_uncertainties={"a": 0.2, "b": 0.1}, method="monte_carlo", samples=50_000, seed=11)
    first = tm.propagate_uncertainty(lambda a, b: 2.0 * a - 3.0 * b, {"a": 10.0, "b": 4.0}, **kwargs)
    second = tm.propagate_uncertainty(lambda a, b: 2.0 * a - 3.0 * b, {"a": 10.0, "b": 4.0}, **kwargs)
    assert first == second
    expected = math.sqrt((2 * 0.2) ** 2 + (3 * 0.1) ** 2)
    assert first.estimate == pytest.approx(8.0, abs=4 * expected / math.sqrt(50_000))
    assert first.standard_uncertainty == pytest.approx(expected, rel=0.02)
    assert first.interval_high - first.interval_low == pytest.approx(2 * 1.96 * expected, rel=0.03)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(covariance=[[1.0, 2.0], [2.0, 1.0]]),
        dict(covariance=[[1.0, 0.5], [0.4, 1.0]]),
        dict(standard_uncertainties={"a": 0.1}),
        dict(standard_uncertainties={"a": 0.1, "b": 0.1}, covariance=[[1, 0], [0, 1]]),
        dict(standard_uncertainties={"a": -0.1, "b": 0.1}),
        dict(standard_uncertainties={"a": 0.1, "b": 0.1}, method="bayes"),
        dict(standard_uncertainties={"a": 0.1, "b": 0.1}, confidence_level=0.4),
        dict(standard_uncertainties={"a": 0.1, "b": 0.1}, method="monte_carlo", samples=10),
    ],
)
def test_invalid_uncertainty_configuration_is_rejected(kwargs):
    with pytest.raises(UncertaintyError):
        tm.propagate_uncertainty(lambda a, b: a + b, {"a": 1.0, "b": 2.0}, **kwargs)


def test_domain_errors_are_reported():
    with pytest.raises(UncertaintyError, match="equation evaluation failed for nominal inputs"):
        tm.propagate_uncertainty(lambda x: math.sqrt(x), {"x": -1.0}, standard_uncertainties={"x": 0.1})
    with pytest.raises(UncertaintyError, match="Monte Carlo evaluation failed"):
        tm.propagate_uncertainty(
            lambda x: math.sqrt(x), {"x": 0.01}, standard_uncertainties={"x": 1.0}, method="monte_carlo", samples=1000
        )


def test_result_to_dict_round_trips_fields():
    result = tm.propagate_uncertainty(
        lambda x: 3.0 * x,
        {"x": 2.0},
        standard_uncertainties={"x": 0.1},
    )
    payload = result.to_dict()
    assert payload["estimate"] == pytest.approx(6.0)
    assert payload["standard_uncertainty"] == pytest.approx(0.3)
    assert payload["interval"] == [result.interval_low, result.interval_high]
    assert payload["method"] == "first_order"
    assert payload["input_names"] == ["x"]
    assert payload["sensitivity_coefficients"] == pytest.approx({"x": 3.0})
    assert payload["sample_count"] == 0


def test_non_callable_function_raises_type_error():
    with pytest.raises(TypeError, match="function must be callable"):
        tm.propagate_uncertainty(None, {"x": 1.0}, standard_uncertainties={"x": 0.1})  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("inputs", "kwargs", "match"),
    [
        ({}, dict(standard_uncertainties={}), "inputs must be a non-empty mapping"),
        ({1: 1.0}, dict(standard_uncertainties={1: 0.1}), "input names must be strings"),
        ({"": 1.0}, dict(standard_uncertainties={"": 0.1}), "input names must be non-empty and distinct"),
        ({" x ": 1.0}, dict(standard_uncertainties={" x ": 0.1}), "input names must be non-empty and distinct"),
        (
            {f"x{i}": 1.0 for i in range(33)},
            dict(standard_uncertainties={f"x{i}": 0.1 for i in range(33)}),
            "at most 32 uncertain inputs are supported",
        ),
        ({"x": True}, dict(standard_uncertainties={"x": 0.1}), "input 'x' must be a finite real number"),
        ({"x": [1.0]}, dict(standard_uncertainties={"x": 0.1}), "input 'x' must be a finite real number"),
        ({"x": "bad"}, dict(standard_uncertainties={"x": 0.1}), "input 'x' must be a finite real number"),
        ({"x": math.nan}, dict(standard_uncertainties={"x": 0.1}), "input 'x' must be a finite real number"),
        (
            {"x": 1.0},
            dict(standard_uncertainties={"x": 1e200}),
            "standard uncertainties are too large to form finite variances",
        ),
        ({"x": 1.0}, dict(covariance=[["bad"]]), "covariance must be a numeric square matrix"),
        (
            {"x": 1.0, "y": 2.0},
            dict(covariance=[[1.0, 0.0]]),
            "covariance must be a finite square matrix ordered like inputs",
        ),
        (
            {"x": 1.0},
            dict(covariance=[[math.inf]]),
            "covariance must be a finite square matrix ordered like inputs",
        ),
        (
            {"x": 1.0, "y": 2.0},
            dict(covariance=[[1.0, 0.5], [0.4, 1.0]]),
            "covariance matrix must be symmetric",
        ),
        (
            {"x": 1.0, "y": 2.0},
            dict(covariance=[[1.0, 2.0], [2.0, 1.0]]),
            "covariance matrix must be positive semidefinite",
        ),
        (
            {"x": 1.0},
            dict(standard_uncertainties={"x": 0.1}, confidence_level=0.95, relative_step=0.0),
            "relative_step must be greater than 0 and less than 0.1",
        ),
        (
            {"x": 1.0},
            dict(standard_uncertainties={"x": 0.1}, confidence_level=0.95, relative_step=0.2),
            "relative_step must be greater than 0 and less than 0.1",
        ),
        (
            {"x": 1e-320},
            dict(standard_uncertainties={"x": 0.0}, relative_step=1e-10),
            "could not choose a finite difference step for 'x'",
        ),
        (
            {"x": 1.0},
            dict(standard_uncertainties={"x": 0.1}, method="monte_carlo", samples="bad"),
            "samples must be an integer between 100 and 100000",
        ),
        (
            {"x": 1.0},
            dict(standard_uncertainties={"x": 0.1}, method="monte_carlo", samples=True),
            "samples must be an integer between 100 and 100000",
        ),
        (
            {"x": 1.0},
            dict(standard_uncertainties={"x": 0.1}, method="monte_carlo", samples=100, seed=True),
            "seed must be an integer or None",
        ),
        (
            {"x": 1.0},
            dict(standard_uncertainties={"x": 0.1}, method="monte_carlo", samples=100, seed="bad"),
            "seed must be an integer or None",
        ),
    ],
)
def test_input_and_parameter_validation_errors(inputs, kwargs, match):
    with pytest.raises(UncertaintyError, match=match):
        tm.propagate_uncertainty(lambda **kw: sum(kw.values()), inputs, **kwargs)


def test_nearly_singular_covariance_clips_tiny_negative_eigenvalue():
    cov = [[1.0, 1.0], [1.0, 1.0 - 1e-13]]
    result = tm.propagate_uncertainty(lambda a, b: a + b, {"a": 0.0, "b": 0.0}, covariance=cov)
    assert result.standard_uncertainty == pytest.approx(2.0, rel=1e-6)


def test_one_sided_finite_difference_fallbacks_and_failure():
    def right_only(x: float) -> float:
        if x < 1.0:
            raise ValueError("undefined below 1")
        return x * x

    forward = tm.propagate_uncertainty(right_only, {"x": 1.0}, standard_uncertainties={"x": 0.1})
    assert forward.sensitivity_coefficients["x"] == pytest.approx(2.0, rel=1e-4)
    assert forward.standard_uncertainty == pytest.approx(0.2, rel=1e-4)

    def left_only(x: float) -> float:
        if x > 1.0:
            raise ValueError("undefined above 1")
        return x * x

    backward = tm.propagate_uncertainty(left_only, {"x": 1.0}, standard_uncertainties={"x": 0.1})
    assert backward.sensitivity_coefficients["x"] == pytest.approx(2.0, rel=1e-4)
    assert backward.standard_uncertainty == pytest.approx(0.2, rel=1e-4)

    def point_only(x: float) -> float:
        if x != 1.0:
            raise ValueError("undefined away from 1")
        return x * x

    with pytest.raises(UncertaintyError, match="cannot estimate sensitivity for 'x' near the supplied input"):
        tm.propagate_uncertainty(point_only, {"x": 1.0}, standard_uncertainties={"x": 0.1})


def test_zero_input_and_zero_uncertainty_uses_unit_step_scale():
    result = tm.propagate_uncertainty(lambda x: 5.0 * x, {"x": 0.0}, standard_uncertainties={"x": 0.0})
    assert result.estimate == pytest.approx(0.0)
    assert result.standard_uncertainty == pytest.approx(0.0)
    assert result.sensitivity_coefficients["x"] == pytest.approx(5.0)


def test_non_finite_sensitivity_and_variance_are_rejected():
    with pytest.raises(UncertaintyError, match="sensitivity for 'x' is non-finite"):
        tm.propagate_uncertainty(
            lambda x: 1e308 if x >= 1.0 else -1e308,
            {"x": 1.0},
            standard_uncertainties={"x": 0.1},
        )

    with pytest.raises(UncertaintyError, match="propagated variance is non-finite"):
        tm.propagate_uncertainty(
            lambda x: 1e154 * x,
            {"x": 1.0},
            standard_uncertainties={"x": 10.0},
        )


@pytest.mark.parametrize("bad_output", [[1.0, 2.0], True, "not-a-number", math.nan, math.inf])
def test_non_scalar_or_non_finite_equation_outputs_are_rejected(bad_output):
    with pytest.raises(UncertaintyError, match="equation output for nominal inputs must be a finite scalar number"):
        tm.propagate_uncertainty(lambda x: bad_output, {"x": 1.0}, standard_uncertainties={"x": 0.1})
