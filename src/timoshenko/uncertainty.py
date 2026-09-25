"""Uncertainty propagation for user-supplied scalar engineering equations."""

from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import NormalDist
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import numpy as np


class UncertaintyError(ValueError):
    """Raised when uncertainty inputs or equation evaluations are invalid."""


@dataclass(frozen=True)
class UncertaintyResult:
    """Scalar estimate and propagated uncertainty with method provenance."""

    estimate: float
    standard_uncertainty: float
    confidence_level: float
    interval_low: float
    interval_high: float
    method: str
    input_names: tuple[str, ...]
    sensitivity_coefficients: Mapping[str, float]
    sample_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_names", tuple(self.input_names))
        object.__setattr__(self, "sensitivity_coefficients", MappingProxyType(dict(self.sensitivity_coefficients)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimate": self.estimate,
            "standard_uncertainty": self.standard_uncertainty,
            "confidence_level": self.confidence_level,
            "interval": [self.interval_low, self.interval_high],
            "method": self.method,
            "input_names": list(self.input_names),
            "sensitivity_coefficients": dict(self.sensitivity_coefficients),
            "sample_count": self.sample_count,
        }


def propagate(
    function: Callable[..., float],
    inputs: Mapping[str, float],
    *,
    standard_uncertainties: Mapping[str, float] | None = None,
    covariance: Sequence[Sequence[float]] | None = None,
    method: str = "first_order",
    confidence_level: float = 0.95,
    relative_step: float = 1e-5,
    samples: int = 10_000,
    seed: int | None = 0,
) -> UncertaintyResult:
    """Propagate input standard uncertainties through a scalar callable.

    ``inputs`` names are passed to ``function`` as keyword arguments. Supply
    either independent ``standard_uncertainties`` by name or a full covariance
    matrix ordered like ``inputs``. ``first_order`` uses centered finite
    differences and the GUM linearized covariance law. ``monte_carlo`` draws
    from the multivariate normal distribution described by the same input
    estimates and covariance. The caller remains responsible for choosing
    suitable input uncertainty models and units.
    """
    if not callable(function):
        raise TypeError("function must be callable")
    if not isinstance(inputs, Mapping) or not inputs:
        raise UncertaintyError("inputs must be a non-empty mapping of keyword names to values")
    if any(not isinstance(name, str) for name in inputs):
        raise UncertaintyError("input names must be strings")
    names = tuple(name.strip() for name in inputs)
    if any(not name or name != original for name, original in zip(names, inputs)) or len(set(names)) != len(names):
        raise UncertaintyError("input names must be non-empty and distinct")
    if len(names) > 32:
        raise UncertaintyError("at most 32 uncertain inputs are supported")
    values = np.asarray([_finite_scalar(inputs[key], f"input {key!r}") for key in inputs], dtype=float)
    if (standard_uncertainties is None) == (covariance is None):
        raise UncertaintyError("supply exactly one of standard_uncertainties or covariance")
    if standard_uncertainties is not None:
        if not isinstance(standard_uncertainties, Mapping) or set(standard_uncertainties) != set(inputs):
            raise UncertaintyError("standard_uncertainties must provide one value for every input name")
        deviations = np.asarray(
            [_finite_scalar(standard_uncertainties[key], f"standard uncertainty for {key!r}") for key in inputs],
            dtype=float,
        )
        if np.any(deviations < 0.0):
            raise UncertaintyError("standard uncertainties must be non-negative")
        with np.errstate(over="ignore", invalid="ignore"):
            covariance_matrix = np.diag(deviations * deviations)
        if not np.isfinite(covariance_matrix).all():
            raise UncertaintyError("standard uncertainties are too large to form finite variances")
    else:
        try:
            covariance_matrix = np.asarray(covariance, dtype=float)
        except (TypeError, ValueError) as error:
            raise UncertaintyError("covariance must be a numeric square matrix") from error
        if covariance_matrix.shape != (len(names), len(names)) or not np.isfinite(covariance_matrix).all():
            raise UncertaintyError("covariance must be a finite square matrix ordered like inputs")
        scale = max(float(np.max(np.abs(covariance_matrix))), np.finfo(float).tiny)
        if not np.allclose(covariance_matrix, covariance_matrix.T, rtol=1e-10, atol=1e-12 * scale):
            raise UncertaintyError("covariance matrix must be symmetric")
        covariance_matrix = 0.5 * (covariance_matrix + covariance_matrix.T)
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)
        except np.linalg.LinAlgError as error:
            raise UncertaintyError("could not validate covariance matrix") from error
        if float(eigenvalues[0]) < -1e-10 * scale:
            raise UncertaintyError("covariance matrix must be positive semidefinite")
        if np.any(eigenvalues < 0.0):
            covariance_matrix = (eigenvectors * np.maximum(eigenvalues, 0.0)) @ eigenvectors.T

    confidence = _finite_scalar(confidence_level, "confidence_level")
    if not 0.5 < confidence < 1.0:
        raise UncertaintyError("confidence_level must be greater than 0.5 and less than 1")
    method_value = str(method).strip().lower()
    if method_value not in {"first_order", "monte_carlo"}:
        raise UncertaintyError("method must be 'first_order' or 'monte_carlo'")
    nominal = _evaluate(function, names, values, "nominal inputs")

    if method_value == "first_order":
        step_scale = _finite_scalar(relative_step, "relative_step")
        if not 0.0 < step_scale < 0.1:
            raise UncertaintyError("relative_step must be greater than 0 and less than 0.1")
        deviations = np.sqrt(np.maximum(np.diag(covariance_matrix), 0.0))
        sensitivities: dict[str, float] = {}
        for index, name in enumerate(names):
            scale = max(abs(float(values[index])), float(deviations[index]))
            if scale == 0.0:
                scale = 1.0
            step = step_scale * scale
            if step == 0.0 or not math.isfinite(step):
                raise UncertaintyError(f"could not choose a finite difference step for {name!r}")
            plus, minus = values.copy(), values.copy()
            plus[index] += step
            minus[index] -= step
            y_plus = _try_evaluate(function, names, plus)
            y_minus = _try_evaluate(function, names, minus)
            if y_plus is not None and y_minus is not None:
                derivative = (y_plus - y_minus) / (2.0 * step)
            elif y_plus is not None:
                derivative = (y_plus - nominal) / step
            elif y_minus is not None:
                derivative = (nominal - y_minus) / step
            else:
                raise UncertaintyError(f"cannot estimate sensitivity for {name!r} near the supplied input")
            if not math.isfinite(derivative):
                raise UncertaintyError(f"sensitivity for {name!r} is non-finite")
            sensitivities[name] = float(derivative)
        gradient = np.asarray([sensitivities[name] for name in names], dtype=float)
        with np.errstate(over="ignore", invalid="ignore"):
            variance = float(gradient @ covariance_matrix @ gradient)
            variance_scale = float(np.abs(gradient) @ np.abs(covariance_matrix) @ np.abs(gradient))
        if not math.isfinite(variance) or not math.isfinite(variance_scale):
            raise UncertaintyError("propagated variance is non-finite")
        if variance < -1e-12 * max(variance_scale, np.finfo(float).tiny):
            raise UncertaintyError("propagated variance became negative")
        standard = math.sqrt(max(variance, 0.0))
        coverage = NormalDist().inv_cdf(0.5 + confidence / 2.0)
        low, high = nominal - coverage * standard, nominal + coverage * standard
        if not all(math.isfinite(value) for value in (standard, low, high)):
            raise UncertaintyError("uncertainty interval is non-finite")
        return UncertaintyResult(
            estimate=nominal,
            standard_uncertainty=standard,
            confidence_level=confidence,
            interval_low=low,
            interval_high=high,
            method=method_value,
            input_names=names,
            sensitivity_coefficients=sensitivities,
            sample_count=0,
        )

    try:
        sample_count = int(samples)
    except (TypeError, ValueError, OverflowError) as error:
        raise UncertaintyError("samples must be an integer between 100 and 100000") from error
    if isinstance(samples, bool) or sample_count != samples or not 100 <= sample_count <= 100_000:
        raise UncertaintyError("samples must be an integer between 100 and 100000")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, (int, np.integer))):
        raise UncertaintyError("seed must be an integer or None")
    try:
        rng = np.random.default_rng(seed)
        draws = rng.multivariate_normal(
            values,
            covariance_matrix,
            size=sample_count,
            check_valid="raise",
            method="eigh",
        )
    except (ValueError, np.linalg.LinAlgError) as error:
        raise UncertaintyError(f"could not sample the configured input distribution: {error}") from error
    output = np.empty(sample_count, dtype=float)
    for index, draw in enumerate(draws):
        try:
            output[index] = _evaluate(function, names, draw, f"Monte Carlo sample {index}")
        except UncertaintyError as error:
            raise UncertaintyError(
                f"Monte Carlo evaluation failed at sample {index}; choose an input distribution whose samples stay in the equation domain"
            ) from error
    estimate = float(np.mean(output))
    standard = float(np.std(output, ddof=1))
    alpha = (1.0 - confidence) / 2.0
    low, high = (float(value) for value in np.quantile(output, [alpha, 1.0 - alpha]))
    if not all(math.isfinite(value) for value in (estimate, standard, low, high)):
        raise UncertaintyError("Monte Carlo summary contains a non-finite value")
    return UncertaintyResult(
        estimate=estimate,
        standard_uncertainty=standard,
        confidence_level=confidence,
        interval_low=low,
        interval_high=high,
        method=method_value,
        input_names=names,
        sensitivity_coefficients={},
        sample_count=sample_count,
    )


def _finite_scalar(value: Any, label: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not np.isscalar(value):
        raise UncertaintyError(f"{label} must be a finite real number")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise UncertaintyError(f"{label} must be a finite real number") from error
    if not math.isfinite(result):
        raise UncertaintyError(f"{label} must be a finite real number")
    return result


def _evaluate(function: Callable[..., float], names: tuple[str, ...], values: Sequence[float], label: str) -> float:
    try:
        result = function(**dict(zip(names, values)))
    except Exception as error:
        raise UncertaintyError(f"equation evaluation failed for {label}: {error}") from error
    if isinstance(result, (bool, np.bool_)) or not np.isscalar(result):
        raise UncertaintyError(f"equation output for {label} must be a finite scalar number")
    try:
        output = float(result)
    except (TypeError, ValueError) as error:
        raise UncertaintyError(f"equation output for {label} must be a finite scalar number") from error
    if not math.isfinite(output):
        raise UncertaintyError(f"equation output for {label} must be a finite scalar number")
    return output


def _try_evaluate(function: Callable[..., float], names: tuple[str, ...], values: Sequence[float]) -> float | None:
    try:
        return _evaluate(function, names, values, "finite difference input")
    except UncertaintyError:
        return None


__all__ = ["UncertaintyError", "UncertaintyResult", "propagate"]
