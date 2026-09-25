"""Regularly sampled, aligned observations from multiple sensor channels."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import math
from pathlib import Path
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class MultiChannelData:
    """Aligned array shaped ``(sample, channel)`` with explicit metadata.

    Input values are copied once into a C-contiguous float64 array so later
    caller mutations cannot silently change a completed analysis input.
    """

    samples: Sequence[Sequence[float]] | np.ndarray
    sampling_hz: float
    channel_ids: Sequence[str]
    units: Sequence[str]

    def __post_init__(self) -> None:
        values = np.asarray(self.samples, dtype=np.float64)
        if values.ndim != 2:
            raise ValueError("samples must be a 2D array shaped (sample, channel)")
        channels = tuple(str(item).strip() for item in self.channel_ids)
        units = tuple(str(item).strip() for item in self.units)
        hz = float(self.sampling_hz)
        if values.shape[0] < 8 or values.shape[1] < 2:
            raise ValueError("at least 8 samples and 2 channels are required")
        if values.shape[1] > 32:
            raise ValueError("at most 32 channels are accepted per analysis to bound memory use")
        if len(channels) != values.shape[1] or len(units) != values.shape[1]:
            raise ValueError("channel_ids and units must have one entry per channel")
        if any(not item for item in channels) or len(set(channels)) != len(channels):
            raise ValueError("channel_ids must be non-empty and unique")
        if any(not item for item in units):
            raise ValueError("units must be non-empty")
        if not math.isfinite(hz) or hz <= 0.0:
            raise ValueError("sampling_hz must be finite and greater than zero")
        if not np.isfinite(values).all():
            raise ValueError("all sensor samples must be finite")
        frozen = np.array(values, dtype=np.float64, order="C", copy=True)
        frozen.setflags(write=False)
        object.__setattr__(self, "samples", frozen)
        object.__setattr__(self, "channel_ids", channels)
        object.__setattr__(self, "units", units)
        object.__setattr__(self, "sampling_hz", hz)

    @property
    def sample_count(self) -> int:
        return int(self.samples.shape[0])

    @property
    def channel_count(self) -> int:
        return int(self.samples.shape[1])


def load_multichannel_csv(
    source: str | Path,
    *,
    columns: Sequence[str],
    sampling_hz: float,
    units: Sequence[str] | None = None,
) -> MultiChannelData:
    """Read aligned numeric channels from a headered CSV file.

    Blank or invalid values are rejected instead of interpolated. Timestamps
    and asynchronous/resampled data are not inferred in this release.
    """
    names = tuple(str(name).strip() for name in columns)
    if len(names) < 2 or any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError("columns must contain at least two distinct non-empty CSV headings")
    unit_names = tuple(units) if units is not None else tuple("unknown" for _ in names)
    if len(unit_names) != len(names):
        raise ValueError("units must contain one entry per selected column")
    data: list[list[float]] = []
    with Path(source).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headings = reader.fieldnames or []
        missing = [name for name in names if name not in headings]
        if missing:
            raise ValueError(f"CSV columns not found: {missing}; available columns are {headings}")
        for row_number, row in enumerate(reader, start=2):
            record: list[float] = []
            for name in names:
                raw = row.get(name)
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    raise ValueError(f"CSV row {row_number} has a missing/non-numeric value in {name!r}") from None
                if not math.isfinite(value):
                    raise ValueError(f"CSV row {row_number} has a non-finite value in {name!r}")
                record.append(value)
            data.append(record)
    return MultiChannelData(data, sampling_hz=sampling_hz, channel_ids=names, units=unit_names)
