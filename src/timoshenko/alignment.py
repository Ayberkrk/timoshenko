"""Explicit timestamp alignment and calibration for asynchronous sensor channels."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np

from .multichannel import MultiChannelData


@dataclass(frozen=True)
class TimedChannel:
    """One channel with its own event timestamps and declared measurement unit."""

    channel_id: str
    unit: str
    timestamps_s: Sequence[float]
    samples: Sequence[float]

    def __post_init__(self) -> None:
        channel_id, unit = str(self.channel_id).strip(), str(self.unit).strip()
        times = np.asarray(self.timestamps_s, dtype=np.float64)
        values = np.asarray(self.samples, dtype=np.float64)
        if not channel_id or not unit:
            raise ValueError("channel_id and unit must be non-empty")
        if times.ndim != 1 or values.ndim != 1 or len(times) != len(values) or len(times) < 8:
            raise ValueError(
                "timestamps_s and samples must be equal-length 1D arrays with at least 8 values"
            )
        if not np.isfinite(times).all() or not np.isfinite(values).all():
            raise ValueError("timestamps and samples must be finite")
        if np.any(np.diff(times) <= 0.0):
            raise ValueError("timestamps_s must be strictly increasing")
        frozen_times = np.array(times, copy=True)
        frozen_values = np.array(values, copy=True)
        frozen_times.setflags(write=False)
        frozen_values.setflags(write=False)
        object.__setattr__(self, "channel_id", channel_id)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "timestamps_s", frozen_times)
        object.__setattr__(self, "samples", frozen_values)


@dataclass(frozen=True)
class AlignedSegment:
    """A contiguous synchronized segment and its shared Unix-second grid."""

    data: MultiChannelData
    timestamps_s: tuple[float, ...]


@dataclass(frozen=True)
class AlignmentResult:
    """Contiguous aligned segments; gaps are preserved as segment boundaries."""

    segments: tuple[AlignedSegment, ...]
    sampling_hz: float
    channel_ids: tuple[str, ...]
    units: tuple[str, ...]
    dropped_grid_points: int
    notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "sampling_hz": self.sampling_hz,
            "channel_ids": list(self.channel_ids),
            "units": list(self.units),
            "dropped_grid_points": self.dropped_grid_points,
            "segments": [
                {
                    "sample_count": segment.data.sample_count,
                    "start_timestamp_s": segment.timestamps_s[0],
                    "end_timestamp_s": segment.timestamps_s[-1],
                }
                for segment in self.segments
            ],
            "notes": list(self.notes),
        }


def align_multichannel(
    channels: Sequence[TimedChannel],
    *,
    sampling_hz: float,
    time_offsets_s: Mapping[str, float] | None = None,
    calibration_scales: Mapping[str, float] | None = None,
    calibration_offsets: Mapping[str, float] | None = None,
    max_gap_s: float | None = None,
    sinc_half_width: int = 8,
) -> AlignmentResult:
    """Synchronize irregularly timed channels using windowed-sinc resampling.

    Explicit ``time_offsets_s`` are added to each channel's timestamps. Values
    are calibrated as ``scale * raw + offset`` before resampling. Each channel
    must already use the same engineering unit after that conversion; this
    function does not infer clock corrections or dimensional unit conversions.
    The target rate may not exceed the slowest input rate. A windowed-sinc
    low-pass reconstruction suppresses content above the target Nyquist limit.
    Grid points whose interpolation stencil would cross a gap larger than
    ``max_gap_s`` are omitted, and each remaining contiguous run is returned
    separately. No gap is interpolated across.
    """
    items = tuple(channels)
    if (
        len(items) < 2
        or len(items) > 32
        or any(not isinstance(item, TimedChannel) for item in items)
    ):
        raise ValueError("channels must contain 2 to 32 TimedChannel instances")
    ids = tuple(item.channel_id for item in items)
    units = tuple(item.unit for item in items)
    if len(set(ids)) != len(ids):
        raise ValueError("channel_id values must be unique")
    if len(set(units)) != 1:
        raise ValueError("channels must use a common unit after calibration")
    rate = float(sampling_hz)
    if not math.isfinite(rate) or rate <= 0.0:
        raise ValueError("sampling_hz must be finite and positive")
    half_width = int(sinc_half_width)
    if (
        isinstance(sinc_half_width, bool)
        or half_width != sinc_half_width
        or not 4 <= half_width <= 32
    ):
        raise ValueError("sinc_half_width must be an integer between 4 and 32")
    offsets = dict(time_offsets_s or {})
    scales = dict(calibration_scales or {})
    value_offsets = dict(calibration_offsets or {})
    known = set(ids)
    if any(key not in known for key in (*offsets, *scales, *value_offsets)):
        raise ValueError("time and calibration mappings may only name configured channels")
    corrected = []
    rates = []
    for item in items:
        time_offset = float(offsets.get(item.channel_id, 0.0))
        scale = float(scales.get(item.channel_id, 1.0))
        value_offset = float(value_offsets.get(item.channel_id, 0.0))
        if (
            not all(math.isfinite(value) for value in (time_offset, scale, value_offset))
            or scale == 0.0
        ):
            raise ValueError(
                "time offsets and calibration values must be finite; scales must be non-zero"
            )
        times = np.asarray(item.timestamps_s) + time_offset
        values = np.asarray(item.samples) * scale + value_offset
        intervals = np.diff(times)
        median_interval = float(np.median(intervals))
        source_rate = 1.0 / median_interval
        if rate > source_rate * (1.0 + 1e-9):
            raise ValueError("target sampling_hz cannot exceed the slowest input channel rate")
        rates.append((source_rate, median_interval))
        corrected.append((times, values, intervals))
    if max_gap_s is None:
        gap_limit = 1.5 * max(interval for _, interval in rates)
    else:
        gap_limit = float(max_gap_s)
        if not math.isfinite(gap_limit) or gap_limit <= 0.0:
            raise ValueError("max_gap_s must be finite and positive")

    # Keep the grid on a stable global sample lattice, then restrict to overlap.
    start = max(float(times[0]) for times, _, _ in corrected)
    end = min(float(times[-1]) for times, _, _ in corrected)
    first_index = math.ceil(start * rate - 1e-9)
    last_index = math.floor(end * rate + 1e-9)
    if last_index - first_index + 1 < 8:
        raise ValueError("channels have fewer than 8 overlapping target grid points")
    grid = np.arange(first_index, last_index + 1, dtype=float) / rate
    matrix = np.empty((len(grid), len(items)), dtype=float)
    valid = np.ones(len(grid), dtype=bool)
    for column, (times, values, intervals) in enumerate(corrected):
        positions = np.searchsorted(times, grid, side="right")
        right = np.clip(positions, 1, len(times) - 1)
        left = right - 1
        bracket_gap = times[right] - times[left]
        local_valid = bracket_gap <= gap_limit
        local_valid &= (grid >= times[0]) & (grid <= times[-1])
        for point_index, right_index in enumerate(right):
            stencil_start = max(0, int(right_index) - half_width)
            stencil_stop = min(len(times), int(right_index) + half_width + 1)
            if np.any(np.diff(times[stencil_start:stencil_stop]) > gap_limit):
                local_valid[point_index] = False
        valid &= local_valid
        median_interval = float(np.median(intervals))
        matrix[:, column] = _windowed_sinc(
            times, values, grid, right, median_interval, rate, half_width
        )

    runs = _contiguous_runs(valid)
    segments: list[AlignedSegment] = []
    for begin, finish in runs:
        if finish - begin < 8:
            continue
        segment_grid = grid[begin:finish]
        data = MultiChannelData(
            matrix[begin:finish],
            sampling_hz=rate,
            channel_ids=ids,
            units=units,
        )
        segments.append(AlignedSegment(data, tuple(float(value) for value in segment_grid)))
    if not segments:
        raise ValueError("no contiguous aligned segment contains at least 8 grid points")
    return AlignmentResult(
        segments=tuple(segments),
        sampling_hz=rate,
        channel_ids=ids,
        units=units,
        dropped_grid_points=int(np.count_nonzero(~valid)),
        notes=(
            "A finite Kaiser-windowed sinc stencil is used; boundary transients are possible within sinc_half_width source samples.",
            "No extrapolation or gap filling is performed; short valid runs with fewer than 8 samples are discarded.",
            "Clock offsets and calibration coefficients are caller-supplied; they are not estimated from the signals.",
        ),
    )


def _windowed_sinc(
    times: np.ndarray,
    values: np.ndarray,
    grid: np.ndarray,
    right_indices: np.ndarray,
    median_interval: float,
    target_hz: float,
    half_width: int,
) -> np.ndarray:
    cutoff = 0.475 * target_hz
    output = np.empty(len(grid), dtype=float)
    for row, (target, right) in enumerate(zip(grid, right_indices, strict=True)):
        center = min(max(int(right), 1), len(times) - 1)
        start = max(0, center - half_width)
        stop = min(len(times), center + half_width + 1)
        delta = target - times[start:stop]
        normalized_distance = delta / (half_width * median_interval)
        window = np.zeros(len(delta), dtype=float)
        inside = np.abs(normalized_distance) < 1.0
        window[inside] = np.i0(8.6 * np.sqrt(1.0 - normalized_distance[inside] ** 2)) / np.i0(8.6)
        kernel = 2.0 * cutoff * median_interval * np.sinc(2.0 * cutoff * delta) * window
        total = float(np.sum(kernel))
        if abs(total) < 1e-12:
            output[row] = np.interp(target, times, values)
        else:
            normalized = kernel / total
            output[row] = float(normalized @ values[start:stop])
    return output


def _contiguous_runs(mask: np.ndarray) -> tuple[tuple[int, int], ...]:
    padded = np.concatenate(([False], mask, [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return tuple(
        (int(start), int(end)) for start, end in zip(changes[::2], changes[1::2], strict=True)
    )


__all__ = ["TimedChannel", "AlignedSegment", "AlignmentResult", "align_multichannel"]
