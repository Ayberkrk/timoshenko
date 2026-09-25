"""Sensor series loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
import csv
import json
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class SensorData:
    """A single regularly sampled sensor channel."""

    samples: tuple[float, ...] | Sequence[float]
    sampling_hz: float
    unit: str = "m/s^2"
    channel: str = "sensor"
    timestamps: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        samples = tuple(float(value) for value in self.samples)
        hz = float(self.sampling_hz)
        if not math.isfinite(hz) or hz <= 0.0:
            raise ValueError("sampling_hz must be finite and greater than zero")
        if len(samples) < 8:
            raise ValueError("at least 8 numeric samples are required")
        if any(not math.isfinite(value) for value in samples):
            raise ValueError("sensor samples must all be finite numeric values")
        timestamps = tuple(float(value) for value in self.timestamps)
        if timestamps and len(timestamps) != len(samples):
            raise ValueError("timestamps must have one entry per sample")
        if any(not math.isfinite(value) for value in timestamps):
            raise ValueError("timestamps must be finite")
        if timestamps and any(right <= left for left, right in zip(timestamps, timestamps[1:])):
            raise ValueError("timestamps must be strictly increasing")
        object.__setattr__(self, "samples", samples)
        object.__setattr__(self, "sampling_hz", hz)
        object.__setattr__(self, "timestamps", timestamps)

    @property
    def duration_seconds(self) -> float:
        return len(self.samples) / self.sampling_hz


def load_sensors(
    source: str | Path | Sequence[float] | SensorData,
    *,
    sampling_hz: float | None = None,
    column: str = "value",
    unit: str = "m/s^2",
    channel: str | None = None,
) -> SensorData:
    """Load one numeric channel from CSV, JSON, an array, or SensorData.

    CSV files need a header matching ``column``. JSON may be a numeric array,
    an object with ``samples``, or an array of objects containing ``column``.
    Sampling frequency must be supplied because 0.1 does not infer time from
    arbitrary file metadata. Blank or non-numeric samples are rejected rather
    than skipped or interpolated.
    """
    if isinstance(source, SensorData):
        if sampling_hz is not None and not math.isclose(float(sampling_hz), source.sampling_hz):
            raise ValueError("sampling_hz conflicts with the supplied SensorData")
        return source
    if sampling_hz is None:
        raise ValueError("sampling_hz is required for sensor input")

    values: list[float]
    source_name = channel or column
    if isinstance(source, (str, Path)):
        path = Path(source)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                # csv.reader rather than DictReader: DictReader silently skips
                # blank lines, which in a one-column file are missing samples.
                # Dropping them would shorten a regularly sampled record and
                # shift every later sample in time.
                reader = csv.reader(handle)
                header = next(reader, [])
                if column not in header:
                    raise ValueError(f"CSV column {column!r} not found; columns are {header}")
                position = header.index(column)
                values = [
                    _parse_numeric(row[position] if position < len(row) else None, reader.line_num)
                    for row in reader
                ]
        elif suffix in {".json", ".jsonl"}:
            text = path.read_text(encoding="utf-8")
            if suffix == ".jsonl":
                payload: Any = [json.loads(line) for line in text.splitlines() if line.strip()]
            else:
                payload = json.loads(text)
            values = _values_from_json(payload, column)
        else:
            raise ValueError("sensor source must be a .csv, .json, or .jsonl file")
        if not channel:
            source_name = path.stem
    else:
        values = [float(value) for value in source]

    return SensorData(
        samples=values,
        sampling_hz=float(sampling_hz),
        unit=unit,
        channel=source_name,
    )


def _parse_numeric(value: Any, line_no: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"sensor input line {line_no} is not numeric: {value!r}") from None
    if not math.isfinite(number):
        raise ValueError(f"sensor input line {line_no} is not finite")
    return number


def _values_from_json(payload: Any, column: str) -> list[float]:
    if isinstance(payload, dict):
        if "samples" in payload:
            payload = payload["samples"]
        elif column in payload:
            payload = payload[column]
        else:
            raise ValueError("JSON object must contain 'samples' or the selected channel key")
    if not isinstance(payload, list):
        raise ValueError("JSON sensor data must be an array")
    values = []
    for idx, item in enumerate(payload, 1):
        if isinstance(item, dict):
            if column not in item:
                raise ValueError(f"JSON sample {idx} has no {column!r} value")
            item = item[column]
        values.append(_parse_numeric(item, idx))
    return values
