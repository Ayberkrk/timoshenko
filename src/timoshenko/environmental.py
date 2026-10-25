"""Linear environmental normalization for repeated modal-frequency records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class EnvironmentalFrequencyBaseline:
    """A fitted linear frequency baseline evaluated at a reference environment.

    ``coefficients_hz_per_unit[mode][feature]`` describes the fitted change in
    modal frequency per unit change in an environmental covariate. The model
    is intended for screening and must be fitted on a representative healthy
    baseline period.
    """

    feature_names: tuple[str, ...]
    reference_environment: tuple[float, ...]
    reference_frequencies_hz: tuple[float, ...]
    coefficients_hz_per_unit: tuple[tuple[float, ...], ...]
    residual_std_hz: tuple[float, ...]
    sample_count: int

    def __post_init__(self) -> None:
        features = tuple(str(name).strip() for name in self.feature_names)
        reference = tuple(float(value) for value in self.reference_environment)
        frequencies = tuple(float(value) for value in self.reference_frequencies_hz)
        coefficients = tuple(tuple(float(value) for value in row) for row in self.coefficients_hz_per_unit)
        residual_std = tuple(float(value) for value in self.residual_std_hz)
        if not features or any(not name for name in features) or len(set(features)) != len(features):
            raise ValueError("feature_names must contain distinct non-empty names")
        if len(reference) != len(features) or not np.isfinite(reference).all():
            raise ValueError("reference_environment must contain one finite value per feature")
        if not frequencies or any(not np.isfinite(value) or value <= 0.0 for value in frequencies):
            raise ValueError("reference_frequencies_hz must contain finite positive values")
        if len(coefficients) != len(frequencies) or any(len(row) != len(features) for row in coefficients):
            raise ValueError("coefficients must have one row per mode and one column per feature")
        if not np.isfinite(np.asarray(coefficients, dtype=float)).all():
            raise ValueError("coefficients must be finite")
        if len(residual_std) != len(frequencies) or any(
            not np.isfinite(value) or value < 0.0 for value in residual_std
        ):
            raise ValueError("residual_std_hz must contain one finite non-negative value per mode")
        if isinstance(self.sample_count, bool) or self.sample_count < len(features) + 2:
            raise ValueError("sample_count must exceed the number of features plus one")
        object.__setattr__(self, "feature_names", features)
        object.__setattr__(self, "reference_environment", reference)
        object.__setattr__(self, "reference_frequencies_hz", frequencies)
        object.__setattr__(self, "coefficients_hz_per_unit", coefficients)
        object.__setattr__(self, "residual_std_hz", residual_std)

    def normalize(self, frequencies_hz: Sequence[float], environment: Sequence[float]) -> tuple[float, ...]:
        """Map measured frequencies to the fitted reference environment."""
        frequencies = np.asarray(tuple(frequencies_hz), dtype=float)
        covariates = np.asarray(tuple(environment), dtype=float)
        if frequencies.shape != (len(self.reference_frequencies_hz),):
            raise ValueError("frequencies_hz must contain one value per fitted mode")
        if covariates.shape != (len(self.feature_names),):
            raise ValueError("environment must contain one value per fitted feature")
        if not np.isfinite(frequencies).all() or np.any(frequencies <= 0.0):
            raise ValueError("frequencies_hz must contain finite positive values")
        if not np.isfinite(covariates).all():
            raise ValueError("environment values must be finite")
        delta = covariates - np.asarray(self.reference_environment)
        coefficients = np.asarray(self.coefficients_hz_per_unit)
        corrected = frequencies - coefficients @ delta
        if not np.isfinite(corrected).all() or np.any(corrected <= 0.0):
            raise ValueError("environmental normalization produced a non-positive frequency")
        return tuple(float(value) for value in corrected)

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_names": list(self.feature_names),
            "reference_environment": list(self.reference_environment),
            "reference_frequencies_hz": list(self.reference_frequencies_hz),
            "coefficients_hz_per_unit": [list(row) for row in self.coefficients_hz_per_unit],
            "residual_std_hz": list(self.residual_std_hz),
            "sample_count": self.sample_count,
        }


def fit_environmental_baseline(
    environmental_covariates: Sequence[Sequence[float]] | np.ndarray,
    measured_frequencies_hz: Sequence[Sequence[float]] | np.ndarray,
    *,
    feature_names: Sequence[str],
) -> EnvironmentalFrequencyBaseline:
    """Fit per-mode linear frequency trends against explicit covariates.

    Inputs are ``(record, feature)`` and ``(record, mode)`` arrays. The fit
    uses ordinary least squares with an intercept and centers the environmental
    covariates at their training mean. It rejects rank-deficient fits and does
    not decide whether the training period is undamaged or representative.
    """
    x = np.asarray(environmental_covariates, dtype=float)
    y = np.asarray(measured_frequencies_hz, dtype=float)
    names = tuple(str(name).strip() for name in feature_names)
    if x.ndim != 2 or y.ndim != 2 or x.shape[0] != y.shape[0]:
        raise ValueError("covariates and frequencies must be 2D arrays with the same record count")
    if x.shape[1] != len(names) or not names or any(not name for name in names):
        raise ValueError("feature_names must name each environmental covariate")
    if len(set(names)) != len(names):
        raise ValueError("feature_names must be distinct")
    if y.shape[1] < 1 or x.shape[0] < x.shape[1] + 2:
        raise ValueError("at least number_of_features + 2 baseline records are required")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(y <= 0.0):
        raise ValueError("baseline inputs must be finite and frequencies must be positive")

    reference_environment = np.mean(x, axis=0)
    design = np.column_stack((np.ones(x.shape[0]), x - reference_environment))
    coefficients, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    if rank != design.shape[1]:
        raise ValueError("environmental covariates are rank-deficient; baseline fit is not identifiable")
    fitted = design @ coefficients
    residual = y - fitted
    return EnvironmentalFrequencyBaseline(
        feature_names=names,
        reference_environment=tuple(float(value) for value in reference_environment),
        reference_frequencies_hz=tuple(float(value) for value in coefficients[0]),
        coefficients_hz_per_unit=tuple(
            tuple(float(value) for value in row) for row in coefficients[1:].T
        ),
        residual_std_hz=tuple(
            float(np.sqrt(np.sum(residual[:, mode] ** 2) / (x.shape[0] - design.shape[1])))
            for mode in range(y.shape[1])
        ),
        sample_count=int(x.shape[0]),
    )


__all__ = ["EnvironmentalFrequencyBaseline", "fit_environmental_baseline"]
