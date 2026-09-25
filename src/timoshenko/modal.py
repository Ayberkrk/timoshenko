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
    resolution, low, high = _plan(
        len(sensor_data.samples),
        sensor_data.sampling_hz,
        max_modes=max_modes,
        min_frequency_hz=min_frequency_hz,
        max_frequency_hz=max_frequency_hz,
        min_peak_ratio=min_peak_ratio,
    )

    values = np.asarray(sensor_data.samples, dtype=float)
    values = values - float(np.mean(values))
    if float(np.max(np.abs(values))) <= np.finfo(float).eps:
        return ModalResult((), sensor_data.sampling_hz, len(values), resolution, sensor_data.channel, status="insufficient_signal", notes=("The input channel is constant after mean removal.",))
    window = np.hanning(len(values))
    spectrum = np.abs(np.fft.rfft(values * window))
    frequencies = np.fft.rfftfreq(len(values), d=1.0 / sensor_data.sampling_hz)
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
    damping_psd = _averaged_psd(values, sensor_data.sampling_hz)
    modes = tuple(
        Mode(
            frequency_hz=float(frequencies[idx]),
            amplitude=float(spectrum[idx]),
            damping_ratio=None if damping_psd is None else _half_power_damping(*damping_psd, float(frequencies[idx])),
        )
        for idx in selected
    )
    notes = ["Frequency spacing is limited by the record duration."] if resolution > 0.25 else []
    if any(mode.damping_ratio is not None for mode in modes):
        notes.append(
            "Damping ratios are coarse half-power screening estimates from an averaged spectrum; "
            "expect scatter of about a factor of two on ambient data."
        )
    if any(mode.damping_ratio is None for mode in modes):
        notes.append(
            "Damping is withheld where the record is too short to resolve the half-power bandwidth "
            f"with {_MIN_DAMPING_AVERAGES} averages and at least {_MIN_DAMPING_BINS:g} frequency bins."
        )
    notes = tuple(notes)
    return ModalResult(
        modes=modes,
        sampling_hz=sensor_data.sampling_hz,
        sample_count=len(values),
        resolution_hz=resolution,
        channel=sensor_data.channel,
        status="ok" if modes else "no_peaks_found",
        notes=notes,
    )


def pair_modes(reference_hz, observed_hz) -> tuple[tuple[int, int], ...]:
    """Pair observed with reference frequencies by nearest log-frequency.

    Each observed frequency is assigned to the reference mode it is closest
    to on a logarithmic scale; when several observed peaks claim the same
    reference mode only the closest one is kept. Returns ``(reference_index,
    observed_index)`` pairs in reference order. Unlike index pairing, a mode
    missed at a sensor node, or a spurious peak, does not shift the comparison
    onto the wrong reference mode. A uniform stiffness change scales every
    frequency by the same factor, so each mode stays nearest to its own
    reference unless the change exceeds the spacing between modes.
    """
    references = [float(value) for value in reference_hz]
    best: dict[int, tuple[float, int]] = {}
    for observed_index, value in enumerate(observed_hz):
        frequency = float(value)
        if not references or not math.isfinite(frequency) or frequency <= 0.0:
            continue
        distances = [abs(math.log(frequency / reference)) for reference in references]
        reference_index = min(range(len(references)), key=distances.__getitem__)
        if reference_index not in best or distances[reference_index] < best[reference_index][0]:
            best[reference_index] = (distances[reference_index], observed_index)
    return tuple((reference_index, best[reference_index][1]) for reference_index in sorted(best))


_MIN_DAMPING_AVERAGES = 8
_MIN_DAMPING_BINS = 4.0


def validate_options(sample_count: int, sampling_hz: float, **options) -> None:
    """Check ``identify`` options for a record length without any data.

    Raises the same errors ``identify`` would raise for these options, so
    long-running callers can reject a bad configuration up front.
    """
    _plan(int(sample_count), float(sampling_hz), **options)


def _plan(
    sample_count: int,
    sampling_hz: float,
    *,
    max_modes: int = 6,
    min_frequency_hz: float | None = None,
    max_frequency_hz: float | None = None,
    min_peak_ratio: float = 0.03,
) -> tuple[float, float, float]:
    """Validate options and return resolution and the searched frequency band."""
    if max_modes < 1:
        raise ValueError("max_modes must be at least one")
    if not 0.0 <= min_peak_ratio < 1.0:
        raise ValueError("min_peak_ratio must be in [0, 1)")
    resolution = sampling_hz / sample_count
    low = float(min_frequency_hz) if min_frequency_hz is not None else resolution
    high = min(float(max_frequency_hz), sampling_hz / 2.0) if max_frequency_hz is not None else sampling_hz / 2.0
    if not math.isfinite(low) or low < 0.0 or not math.isfinite(high) or high <= low:
        raise ValueError("frequency bounds must be finite, non-negative, and have max greater than min")
    return resolution, low, high


def _averaged_psd(values: np.ndarray, sampling_hz: float) -> tuple[np.ndarray, np.ndarray] | None:
    """Welch power spectrum with 50% overlap and at least eight averages.

    A single periodogram of ambient response fluctuates by about 100% per
    bin, so its half-power points land on noise spikes. The segment length is
    the longest power of two that still gives the required averages.
    """
    longest = len(values) / (1.0 + (_MIN_DAMPING_AVERAGES - 1) / 2.0)
    if longest < 64:
        return None
    nperseg = 2 ** int(math.floor(math.log2(longest)))
    window = np.hanning(nperseg)
    power = np.zeros(nperseg // 2 + 1)
    count = 0
    for start in range(0, len(values) - nperseg + 1, nperseg // 2):
        segment = values[start : start + nperseg]
        power += np.abs(np.fft.rfft((segment - np.mean(segment)) * window)) ** 2
        count += 1
    return power / count, np.fft.rfftfreq(nperseg, d=1.0 / sampling_hz)


def _half_power_damping(power: np.ndarray, frequencies: np.ndarray, frequency_hz: float) -> float | None:
    """Half-power bandwidth damping, or ``None`` when it is not resolved.

    A Hann window alone gives a half-power width of about 1.44 bins, so a
    bandwidth narrower than ``_MIN_DAMPING_BINS`` bins describes the window
    and record length rather than the structure.
    """
    resolution = float(frequencies[1] - frequencies[0])
    nearest = int(round(frequency_hz / resolution))
    low, high = max(1, nearest - 1), min(len(power) - 2, nearest + 1)
    if high < low:
        return None
    peak_idx = low + int(np.argmax(power[low : high + 1]))
    half_power = float(power[peak_idx]) / 2.0
    if half_power <= 0.0:
        return None
    f_left: float | None = None
    for idx in range(peak_idx, 0, -1):
        p0, p1 = float(power[idx - 1]), float(power[idx])
        if p0 <= half_power < p1:
            f_left = float(frequencies[idx - 1]) + (half_power - p0) * resolution / (p1 - p0)
            break
    f_right: float | None = None
    for idx in range(peak_idx, len(power) - 1):
        p0, p1 = float(power[idx]), float(power[idx + 1])
        if p0 > half_power >= p1:
            f_right = float(frequencies[idx]) + (p0 - half_power) * resolution / (p0 - p1)
            break
    f_peak = float(frequencies[peak_idx])
    if f_left is None or f_right is None or f_right - f_left < _MIN_DAMPING_BINS * resolution:
        return None
    return min(1.0, (f_right - f_left) / (2.0 * f_peak))
