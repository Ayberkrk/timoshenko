"""Regularized story-by-story stiffness updating for shear-building models."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Sequence

import numpy as np

from .structure import Structure


@dataclass(frozen=True)
class StoryUpdateResult:
    """Result of fitting individual story stiffness scales to all measured modes."""

    updated_structure: Structure
    story_stiffness_scale_factors: tuple[float, ...]
    measured_frequencies_hz: tuple[float, ...]
    fitted_frequencies_hz: tuple[float, ...]
    residual_rms_pct: float
    iterations: int
    converged: bool
    regularization: float

    def to_dict(self) -> dict[str, object]:
        return {
            "structure_id": self.updated_structure.structure_id,
            "story_stiffness_scale_factors": list(self.story_stiffness_scale_factors),
            "measured_frequencies_hz": list(self.measured_frequencies_hz),
            "fitted_frequencies_hz": list(self.fitted_frequencies_hz),
            "residual_rms_pct": self.residual_rms_pct,
            "iterations": self.iterations,
            "converged": self.converged,
            "regularization": self.regularization,
            "updated_story_stiffness_n_m": list(self.updated_structure.story_stiffness_n_m),
        }


def update_story_stiffness(
    structure: Structure,
    measured_frequencies_hz: Sequence[float],
    *,
    regularization: float = 1e-6,
    maximum_iterations: int = 100,
    tolerance: float = 1e-9,
) -> StoryUpdateResult:
    """Estimate individual story stiffness scales from a complete modal set.

    The solver minimizes log-frequency residuals with a Levenberg-Marquardt
    iteration in log stiffness space. A small Tikhonov term favors the supplied
    stiffness model when the modal data are weakly informative. Frequencies
    must already be in corresponding ascending mode order; this function does
    not perform mode pairing or use mode shapes.
    """
    if not isinstance(structure, Structure):
        raise TypeError("structure must be a timoshenko.Structure")
    observed = np.asarray(tuple(measured_frequencies_hz), dtype=float)
    if observed.shape != (structure.story_count,):
        raise ValueError("measured_frequencies_hz must contain one value per story mode")
    if not np.isfinite(observed).all() or np.any(observed <= 0.0):
        raise ValueError("measured frequencies must be finite and positive")
    penalty = float(regularization)
    if not math.isfinite(penalty) or penalty <= 0.0:
        raise ValueError("regularization must be finite and positive")
    if (
        isinstance(maximum_iterations, bool)
        or int(maximum_iterations) != maximum_iterations
        or maximum_iterations < 1
    ):
        raise ValueError("maximum_iterations must be a positive integer")
    tolerance_value = float(tolerance)
    if not math.isfinite(tolerance_value) or tolerance_value <= 0.0:
        raise ValueError("tolerance must be finite and positive")

    initial = np.asarray(structure.story_stiffness_n_m, dtype=float)
    log_scale = np.zeros(structure.story_count, dtype=float)

    def predict(parameters: np.ndarray) -> np.ndarray:
        candidate = replace(
            structure,
            story_stiffness_n_m=tuple(initial * np.exp(parameters)),
            reference_frequencies_hz=(),
            observed_frequencies_hz=(),
            update_scale_factor=None,
            update_mode_count=0,
            update_mode_scale_spread_pct=None,
            update_status="not_updated",
        )
        return np.asarray(candidate.natural_frequencies_hz, dtype=float)

    target = np.log(observed)
    root_penalty = math.sqrt(penalty)

    def residual(parameters: np.ndarray) -> np.ndarray:
        return np.concatenate((np.log(predict(parameters)) - target, root_penalty * parameters))

    damping = 1e-3
    current = residual(log_scale)
    converged = False
    iterations = 0
    for iteration in range(1, int(maximum_iterations) + 1):
        jacobian = np.empty((len(current), len(log_scale)), dtype=float)
        step_size = 1e-5
        for column in range(len(log_scale)):
            offset = np.zeros_like(log_scale)
            offset[column] = step_size
            jacobian[:, column] = (residual(log_scale + offset) - residual(log_scale - offset)) / (
                2.0 * step_size
            )
        gradient = jacobian.T @ current
        if float(np.linalg.norm(gradient, ord=np.inf)) <= tolerance_value:
            converged = True
            iterations = iteration - 1
            break
        normal = jacobian.T @ jacobian
        diagonal = np.maximum(np.diag(normal), 1.0)
        try:
            delta = np.linalg.solve(normal + damping * np.diag(diagonal), -gradient)
        except np.linalg.LinAlgError:
            damping *= 10.0
            if damping > 1e12:
                iterations = iteration
                break
            continue
        candidate_parameters = log_scale + delta
        candidate_residual = residual(candidate_parameters)
        if float(candidate_residual @ candidate_residual) < float(current @ current):
            improvement = float(current @ current - candidate_residual @ candidate_residual)
            log_scale, current = candidate_parameters, candidate_residual
            damping = max(damping / 3.0, 1e-12)
            iterations = iteration
            if float(np.linalg.norm(delta, ord=np.inf)) <= tolerance_value or improvement <= (
                tolerance_value**2
            ):
                converged = True
                break
        else:
            damping *= 10.0
            iterations = iteration
            if damping > 1e12:
                break

    fitted = predict(log_scale)
    scales = np.exp(log_scale)
    updated = replace(
        structure,
        story_stiffness_n_m=tuple(float(value) for value in initial * scales),
        reference_frequencies_hz=structure.baseline_frequencies_hz,
        observed_frequencies_hz=tuple(float(value) for value in observed),
        update_scale_factor=None,
        update_mode_count=structure.story_count,
        update_mode_scale_spread_pct=None,
        update_status="updated_local" if converged else "updated_local_not_converged",
    )
    rms_pct = float(np.sqrt(np.mean((100.0 * (fitted - observed) / observed) ** 2)))
    return StoryUpdateResult(
        updated_structure=updated,
        story_stiffness_scale_factors=tuple(float(value) for value in scales),
        measured_frequencies_hz=tuple(float(value) for value in observed),
        fitted_frequencies_hz=tuple(float(value) for value in fitted),
        residual_rms_pct=rms_pct,
        iterations=iterations,
        converged=converged,
        regularization=penalty,
    )


__all__ = ["StoryUpdateResult", "update_story_stiffness"]
