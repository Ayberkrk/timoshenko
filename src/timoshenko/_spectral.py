"""Small helpers for locating frequency-domain peaks."""

from __future__ import annotations

import math

import numpy as np


def interpolate_log_peak_frequency(
    frequencies: np.ndarray,
    spectrum: np.ndarray,
    peak_index: int,
) -> float:
    """Refine a spectral-bin peak with a three-point log-magnitude parabola."""
    center_frequency = float(frequencies[peak_index])
    if peak_index <= 0 or peak_index >= len(spectrum) - 1:
        return center_frequency
    left = float(spectrum[peak_index - 1])
    center = float(spectrum[peak_index])
    right = float(spectrum[peak_index + 1])
    if not all(math.isfinite(value) and value > 0.0 for value in (left, center, right)):
        return center_frequency

    log_left, log_center, log_right = math.log(left), math.log(center), math.log(right)
    curvature = log_left - 2.0 * log_center + log_right
    if not math.isfinite(curvature) or curvature >= 0.0:
        return center_frequency
    offset = 0.5 * (log_left - log_right) / curvature
    if not math.isfinite(offset):
        return center_frequency
    offset = min(0.5, max(-0.5, offset))
    bin_width = float(frequencies[peak_index + 1] - frequencies[peak_index])
    return center_frequency + offset * bin_width
