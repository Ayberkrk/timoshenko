"""Basic frequency-domain decomposition (FDD) for aligned output channels."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .multichannel import MultiChannelData


@dataclass(frozen=True)
class FDDMode:
    frequency_hz: float
    singular_value: float
    singular_value_index: int
    channel_ids: tuple[str, ...]
    units: tuple[str, ...]
    shape_real: tuple[float, ...]
    shape_imag: tuple[float, ...]
    singular_value_ratio: float

    def to_dict(self) -> dict:
        return {
            "frequency_hz": self.frequency_hz,
            "singular_value": self.singular_value,
            "singular_value_index": self.singular_value_index,
            "channel_ids": list(self.channel_ids),
            "units": list(self.units),
            "mode_shape": [
                {"real": real, "imag": imag} for real, imag in zip(self.shape_real, self.shape_imag)
            ],
            "singular_value_ratio": self.singular_value_ratio,
        }


@dataclass(frozen=True)
class FDDResult:
    modes: tuple[FDDMode, ...]
    sampling_hz: float
    sample_count: int
    resolution_hz: float
    segment_count: int
    nperseg: int
    channel_ids: tuple[str, ...]
    units: tuple[str, ...]
    method: str = "welch_frequency_domain_decomposition"
    status: str = "ok"
    notes: tuple[str, ...] = ()

    @property
    def frequencies_hz(self) -> tuple[float, ...]:
        return tuple(mode.frequency_hz for mode in self.modes)

    def to_dict(self) -> dict:
        return {
            "modes": [mode.to_dict() for mode in self.modes],
            "sampling_hz": self.sampling_hz,
            "sample_count": self.sample_count,
            "resolution_hz": self.resolution_hz,
            "segment_count": self.segment_count,
            "nperseg": self.nperseg,
            "channel_ids": list(self.channel_ids),
            "units": list(self.units),
            "method": self.method,
            "status": self.status,
            "notes": list(self.notes),
        }


def identify_fdd(
    observations: MultiChannelData,
    *,
    nperseg: int | None = None,
    overlap: float = 0.5,
    max_modes: int = 8,
    max_singular_values: int = 4,
    min_frequency_hz: float | None = None,
    max_frequency_hz: float | None = None,
    min_peak_ratio: float = 0.05,
    min_singular_value_ratio: float = 0.05,
) -> FDDResult:
    """Estimate modal frequencies and complex mode shapes with Welch FDD.

    The cross-spectral-density matrix is estimated from mean-removed Hann
    segments, then decomposed frequency-by-frequency. The largest singular
    value curves are searched for local peaks. This is a first-pass FDD
    estimator: it does not use stabilization diagrams, SSI, damping fits,
    environmental normalization, or damage classification.
    """
    if not isinstance(observations, MultiChannelData):
        raise TypeError("observations must be MultiChannelData; use tm.load_multichannel_csv() or construct it explicitly")
    if len(set(observations.units)) != 1:
        raise ValueError("FDD requires channels with the same measurement unit; calibrate/transform mixed-unit channels first")
    if max_modes < 1 or max_singular_values < 1:
        raise ValueError("max_modes and max_singular_values must be positive")
    if not 0.0 <= min_peak_ratio < 1.0:
        raise ValueError("min_peak_ratio must be in [0, 1)")
    if not math.isfinite(float(min_singular_value_ratio)) or not 0.0 <= float(min_singular_value_ratio) <= 1.0:
        raise ValueError("min_singular_value_ratio must be finite and in [0, 1]")
    overlap_value = float(overlap)
    if not math.isfinite(overlap_value) or not 0.0 <= overlap_value <= 0.9:
        raise ValueError("overlap must be finite and in [0, 0.9]")

    sample_count, channel_count = observations.samples.shape
    if nperseg is None:
        available = max(8, min(1024, int(sample_count * (1.0 - overlap_value))))
        nperseg_value = 2 ** int(math.floor(math.log2(available)))
    else:
        nperseg_value = int(nperseg)
    if nperseg_value < 8 or nperseg_value > 4096 or nperseg_value > sample_count:
        raise ValueError("nperseg must be between 8 and min(sample_count, 4096)")
    hop = max(1, int(round(nperseg_value * (1.0 - overlap_value))))
    starts = range(0, sample_count - nperseg_value + 1, hop)
    segment_count = len(starts)
    if segment_count < 2:
        raise ValueError("at least two overlapping FFT segments are required; lower nperseg or overlap less")

    values = observations.samples
    window = np.hanning(nperseg_value)
    window_power = float(np.sum(window**2))
    frequencies = np.fft.rfftfreq(nperseg_value, d=1.0 / observations.sampling_hz)
    frequency_count = len(frequencies)
    retained = min(int(max_singular_values), channel_count)
    spectral_matrices = np.zeros((frequency_count, channel_count, channel_count), dtype=np.complex128)
    for start in starts:
        segment = values[start : start + nperseg_value]
        segment = segment - np.mean(segment, axis=0, keepdims=True)
        spectrum = np.fft.rfft(segment * window[:, None], axis=0)
        spectral_matrices += np.einsum("fc,fd->fcd", spectrum, np.conjugate(spectrum), optimize=True)
    spectral_matrices /= segment_count * observations.sampling_hz * window_power
    if nperseg_value % 2 == 0:
        spectral_matrices[1:-1] *= 2.0
    else:
        spectral_matrices[1:] *= 2.0

    singular = np.zeros((frequency_count, retained), dtype=float)
    vectors = np.zeros((frequency_count, channel_count, retained), dtype=np.complex128)
    for idx in range(frequency_count):
        eigenvalues, eigenvectors = np.linalg.eigh(spectral_matrices[idx])
        order = np.argsort(eigenvalues)[::-1][:retained]
        singular[idx, :] = np.maximum(eigenvalues[order].real, 0.0)
        vectors[idx, :, :] = eigenvectors[:, order]

    resolution = observations.sampling_hz / nperseg_value
    low = float(min_frequency_hz) if min_frequency_hz is not None else resolution
    high = float(max_frequency_hz) if max_frequency_hz is not None else observations.sampling_hz / 2.0
    high = min(high, observations.sampling_hz / 2.0)
    if not math.isfinite(low) or low < 0.0 or not math.isfinite(high) or high <= low:
        raise ValueError("frequency bounds must be finite and non-negative, with max greater than min")
    in_band = (frequencies >= low) & (frequencies <= high)
    leading_peak = float(np.max(singular[in_band, 0])) if np.any(in_band) else 0.0
    candidates: list[tuple[float, int, int]] = []
    for rank in range(retained):
        curve = singular[:, rank]
        curve_max = float(np.max(curve[in_band])) if np.any(in_band) else 0.0
        if curve_max <= 0.0:
            continue
        if rank > 0 and leading_peak > 0.0 and curve_max / leading_peak < min_singular_value_ratio:
            continue
        for idx in range(1, frequency_count - 1):
            rank_ratio = float(curve[idx] / singular[idx, 0]) if singular[idx, 0] > 0.0 else 0.0
            if (
                in_band[idx]
                and curve[idx] >= curve[idx - 1]
                and curve[idx] > curve[idx + 1]
                and curve[idx] >= curve_max * min_peak_ratio
                and rank_ratio >= min_singular_value_ratio
            ):
                candidates.append((float(curve[idx]), rank, idx))
    candidates.sort(reverse=True)
    chosen: list[tuple[float, int, int]] = []
    for candidate in candidates:
        _, rank, idx = candidate
        if all(abs(float(frequencies[idx] - frequencies[other_idx])) >= 2.0 * resolution for _, _, other_idx in chosen):
            chosen.append(candidate)
        if len(chosen) >= max_modes:
            break
    chosen.sort(key=lambda item: float(frequencies[item[2]]))

    modes: list[FDDMode] = []
    for value, rank, idx in chosen:
        shape = vectors[idx, :, rank]
        magnitude = np.abs(shape)
        maximum = float(np.max(magnitude))
        if maximum > 0.0:
            shape = shape / maximum
            phase_reference = int(np.argmax(np.abs(shape)))
            shape = shape * np.exp(-1j * np.angle(shape[phase_reference]))
        modes.append(FDDMode(
            frequency_hz=float(frequencies[idx]),
            singular_value=value,
            singular_value_index=rank + 1,
            channel_ids=tuple(observations.channel_ids),
            units=tuple(observations.units),
            shape_real=tuple(float(item.real) for item in shape),
            shape_imag=tuple(float(item.imag) for item in shape),
            singular_value_ratio=float(value / singular[idx, 0]) if singular[idx, 0] > 0.0 else 0.0,
        ))
    notes = (
        "Frequency resolution is sampling_hz / nperseg; longer windows improve resolution but reduce the number of averages.",
        "Mode-shape components are normalized to unit peak magnitude; their overall scale and phase are arbitrary.",
        "Peaks from different singular-value curves can be missed or duplicated for close/repeated modes; review results against engineering context.",
    )
    return FDDResult(
        modes=tuple(modes),
        sampling_hz=observations.sampling_hz,
        sample_count=int(sample_count),
        resolution_hz=resolution,
        segment_count=segment_count,
        nperseg=nperseg_value,
        channel_ids=tuple(observations.channel_ids),
        units=tuple(observations.units),
        status="ok" if modes else "no_peaks_found",
        notes=notes,
    )
