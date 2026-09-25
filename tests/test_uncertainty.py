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
    with pytest.raises(UncertaintyError):
        tm.propagate_uncertainty(lambda x: math.sqrt(x), {"x": -1.0}, standard_uncertainties={"x": 0.1})
    with pytest.raises(UncertaintyError):
        tm.propagate_uncertainty(
            lambda x: math.sqrt(x), {"x": 0.01}, standard_uncertainties={"x": 1.0}, method="monte_carlo", samples=1000
        )
