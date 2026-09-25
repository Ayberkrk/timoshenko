"""Frequency-domain operational modal identification for one sensor channel."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .sensors import SensorData
from .oma import FDDMode, FDDResult, identify_fdd


@dataclass(frozen=True)
class Mode:
    frequency_hz: float
    amplitude: float
    damping_ratio: float | None = None


@dataclass(frozen=True)
class ModalResult:
    modes: tuple[Mode, ...]
    sampling_hz: float
    sample_count: int
    resolution_hz: float
    channel: str
    method: str = "hann_windowed_fft_peak_picking"
    status: str = "ok"
    notes: tuple[str, ...] = ()

    @property
    def frequencies_hz(self) -> tuple[float, ...]:
        return tuple(mode.frequency_hz for mode in self.modes)

    def to_dict(self) -> dict:
        return {
            "modes": [
                {"frequency_hz": mode.frequency_hz, "amplitude": mode.amplitude, "damping_ratio": mode.damping_ratio}
                for mode in self.modes
            ],
            "sampling_hz": self.sampling_hz,
            "sample_count": self.sample_count,
            "resolution_hz": self.resolution_hz,
            "channel": self.channel,
            "method": self.method,
            "status": self.status,
            "notes": list(self.notes),
        }


def identify(
    sensor_data: SensorData,
    *,
    max_modes: int = 6,
    min_frequency_hz: float | None = None,
    max_frequency_hz: float | None = None,
    min_peak_ratio: float = 0.03,
) -> ModalResult:
    """Estimate modal peaks with a Hann-windowed single-sided FFT.

    This simple operational modal analysis uses one channel, so modes may be
    missed when that sensor is near a modal node. It is intended as a
    screening estimate; poly-reference identification and mode shapes are not
    part of release 0.1.
    """
    if not isinstance(sensor_data, SensorData):
        raise TypeError("sensor_data must be a timoshenko.SensorData; use tm.load_sensors() first")
    if max_modes < 1:
        raise ValueError("max_modes must be at least one")
    if not 0.0 <= min_peak_ratio < 1.0:
        raise ValueError("min_peak_ratio must be in [0, 1)")

    values = np.asarray(sensor_data.samples, dtype=float)
    values = values - float(np.mean(values))
    if float(np.max(np.abs(values))) <= np.finfo(float).eps:
        return ModalResult((), sensor_data.sampling_hz, len(values), sensor_data.sampling_hz / len(values), sensor_data.channel, status="insufficient_signal", notes=("The input channel is constant after mean removal.",))
    window = np.hanning(len(values))
    spectrum = np.abs(np.fft.rfft(values * window))
    frequencies = np.fft.rfftfreq(len(values), d=1.0 / sensor_data.sampling_hz)
    resolution = sensor_data.sampling_hz / len(values)
    low = float(min_frequency_hz) if min_frequency_hz is not None else resolution
    high = min(float(max_frequency_hz), sensor_data.sampling_hz / 2.0) if max_frequency_hz is not None else sensor_data.sampling_hz / 2.0
    if not math.isfinite(low) or low < 0.0 or not math.isfinite(high) or high <= low:
        raise ValueError("frequency bounds must be finite, non-negative, and have max greater than min")
    in_band = (frequencies >= low) & (frequencies <= high)
    candidates = [
        idx for idx in range(1, len(spectrum) - 1)
        if in_band[idx] and spectrum[idx] >= spectrum[idx - 1] and spectrum[idx] > spectrum[idx + 1]
    ]
    max_amplitude = float(max((spectrum[idx] for idx in candidates), default=0.0))
    candidates = [idx for idx in candidates if max_amplitude > 0.0 and spectrum[idx] >= max_amplitude * min_peak_ratio]
    selected: list[int] = []
    for idx in sorted(candidates, key=lambda item: float(spectrum[item]), reverse=True):
        if all(abs(float(frequencies[idx] - frequencies[other])) >= 2.0 * resolution for other in selected):
            selected.append(idx)
        if len(selected) >= max_modes:
            break
    selected.sort(key=lambda item: float(frequencies[item]))
    modes = tuple(
        Mode(
            frequency_hz=float(frequencies[idx]),
            amplitude=float(spectrum[idx]),
            damping_ratio=_half_power_damping(spectrum, frequencies, idx),
        )
        for idx in selected
    )
    notes = ("Frequency spacing is limited by the record duration.",) if resolution > 0.25 else ()
    return ModalResult(
        modes=modes,
        sampling_hz=sensor_data.sampling_hz,
        sample_count=len(values),
        resolution_hz=resolution,
        channel=sensor_data.channel,
        status="ok" if modes else "no_peaks_found",
        notes=notes,
    )


def _half_power_damping(spectrum: np.ndarray, frequencies: np.ndarray, peak_idx: int) -> float | None:
    peak_amplitude = float(spectrum[peak_idx])
    if peak_amplitude <= 0.0:
        return None
    power = np.asarray(spectrum, dtype=float) ** 2
    half_power = float(power[peak_idx]) / 2.0
    f_left: float | None = None
    for idx in range(peak_idx, 0, -1):
        p0, p1 = float(power[idx - 1]), float(power[idx])
        if p0 <= half_power < p1:
            f0, f1 = float(frequencies[idx - 1]), float(frequencies[idx])
            f_left = f0 if p1 == p0 else f0 + (half_power - p0) * (f1 - f0) / (p1 - p0)
            break
    f_right: float | None = None
    for idx in range(peak_idx, len(spectrum) - 1):
        p0, p1 = float(power[idx]), float(power[idx + 1])
        if p0 > half_power >= p1:
            f0, f1 = float(frequencies[idx]), float(frequencies[idx + 1])
            f_right = f0 if p0 == p1 else f0 + (p0 - half_power) * (f1 - f0) / (p0 - p1)
            break
    f_peak = float(frequencies[peak_idx])
    if f_peak <= 0.0 or f_left is None or f_right is None or f_right <= f_left:
        return None
    return max(0.0, min(1.0, (f_right - f_left) / (2.0 * f_peak)))
