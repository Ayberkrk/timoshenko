"""Bounded-memory CSV observation replay source."""

from __future__ import annotations

import csv
from datetime import datetime
import math
from pathlib import Path
from typing import TextIO

from .observations import Observation, ObservationBatch


class CSVSourceError(ValueError):
    """Raised when a CSV file cannot be read as the configured observation schema."""


def _parse_timestamp(value: str) -> float:
    text = value.strip()
    try:
        result = float(text)
    except ValueError:
        iso_text = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
        try:
            parsed = datetime.fromisoformat(iso_text)
        except ValueError as error:
            raise ValueError("timestamp must be Unix seconds or timezone-aware ISO-8601") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("ISO-8601 timestamps must include a timezone")
        result = parsed.timestamp()
    if not math.isfinite(result):
        raise ValueError("timestamp must be finite")
    return result


def _parse_quality(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "good", "valid"}:
        return True
    if normalized in {"0", "false", "no", "bad", "invalid"}:
        return False
    raise ValueError("quality must be one of true/false, 1/0, yes/no, good/bad, or valid/invalid")


class CSVObservationSource:
    """Read long-format sensor CSV incrementally as :class:`ObservationBatch` objects.

    The source never loads the whole file. Column names are explicit, event time
    is required, and every emitted batch has a stable source/row-range identity.
    Numeric timestamps mean Unix seconds; ISO-8601 timestamps must include a
    timezone. All values are preserved in the CSV's declared unit.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        source_id: str | None = None,
        batch_size: int = 256,
        timestamp_column: str = "timestamp",
        sensor_id_column: str = "sensor_id",
        name_column: str | None = "name",
        unit_column: str = "unit",
        value_column: str = "value",
        quality_column: str | None = "quality",
        asset_id_column: str | None = "asset_id",
    ):
        size = int(batch_size)
        if isinstance(batch_size, bool) or size != batch_size or not 1 <= size <= 4096:
            raise ValueError("batch_size must be an integer between 1 and 4096")
        columns = [timestamp_column, sensor_id_column, unit_column, value_column]
        columns.extend(column for column in (name_column, quality_column, asset_id_column) if column is not None)
        normalized = [str(column).strip() for column in columns]
        if any(not column for column in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("configured CSV column names must be non-empty and distinct")
        self.path = Path(path)
        if source_id is None:
            source_value = f"csv:{self.path.name}"
        else:
            source_value = str(source_id).strip()
        if not source_value:
            raise ValueError("source_id must be non-empty")
        self.source_id = source_value
        self.batch_size = size
        self.timestamp_column = str(timestamp_column).strip()
        self.sensor_id_column = str(sensor_id_column).strip()
        self.name_column = None if name_column is None else str(name_column).strip()
        self.unit_column = str(unit_column).strip()
        self.value_column = str(value_column).strip()
        self.quality_column = None if quality_column is None else str(quality_column).strip()
        self.asset_id_column = None if asset_id_column is None else str(asset_id_column).strip()
        self._file: TextIO | None = None
        self._reader: csv.DictReader | None = None
        self._row_sequence = 0

    def open(self) -> None:
        if self._file is not None:
            raise RuntimeError("CSV observation source is already open")
        try:
            file = self.path.open("r", newline="", encoding="utf-8-sig")
        except OSError as error:
            raise CSVSourceError(f"cannot open observation CSV {self.path}: {error}") from error
        reader = csv.DictReader(file, strict=True)
        headers = reader.fieldnames
        if not headers or any(header is None or not header.strip() for header in headers):
            file.close()
            raise CSVSourceError("CSV must contain a header row with non-empty column names")
        if len(set(headers)) != len(headers):
            file.close()
            raise CSVSourceError("CSV header contains duplicate column names")
        required = {
            self.timestamp_column,
            self.sensor_id_column,
            self.unit_column,
            self.value_column,
        }
        required.update(column for column in (self.name_column, self.quality_column, self.asset_id_column) if column is not None)
        missing = required - set(headers)
        if missing:
            file.close()
            raise CSVSourceError(f"CSV is missing configured columns: {', '.join(sorted(missing))}")
        self._file = file
        self._reader = reader
        self._row_sequence = 0

    def read_batch(self) -> ObservationBatch | None:
        if self._reader is None:
            raise RuntimeError("open() must be called before read_batch()")
        rows: list[Observation] = []
        first_row_sequence = self._row_sequence + 1
        while len(rows) < self.batch_size:
            try:
                row = next(self._reader)
            except StopIteration:
                break
            except csv.Error as error:
                raise CSVSourceError(f"malformed CSV near line {self._reader.line_num}: {error}") from error
            line_number = self._reader.line_num
            if None in row:
                raise CSVSourceError(f"row near line {line_number} has more fields than the CSV header")
            if all(value is None or not value.strip() for value in row.values()):
                continue
            try:
                sensor_id = self._required(row, self.sensor_id_column)
                unit = self._required(row, self.unit_column)
                raw_name = sensor_id if self.name_column is None else self._required(row, self.name_column)
                timestamp = _parse_timestamp(self._required(row, self.timestamp_column))
                value = float(self._required(row, self.value_column))
                quality = True if self.quality_column is None else _parse_quality(self._required(row, self.quality_column))
                raw_asset_id = "" if self.asset_id_column is None else (row.get(self.asset_id_column) or "").strip()
                observation = Observation(
                    sensor_id=sensor_id,
                    name=raw_name,
                    unit=unit,
                    value=value,
                    timestamp=timestamp,
                    quality=quality,
                    asset_id=raw_asset_id or None,
                    source_id=self.source_id,
                    metadata={"csv_line": line_number},
                )
            except (TypeError, ValueError) as error:
                raise CSVSourceError(f"invalid observation near CSV line {line_number}: {error}") from error
            rows.append(observation)
            self._row_sequence += 1
        if not rows:
            return None
        return ObservationBatch(
            rows,
            source_id=self.source_id,
            batch_id=f"{self.source_id}:rows:{first_row_sequence}-{self._row_sequence}",
        )

    @staticmethod
    def _required(row: dict[str | None, str | None], column: str) -> str:
        value = row.get(column)
        if value is None or not value.strip():
            raise ValueError(f"{column!r} must not be empty")
        return value.strip()

    def close(self) -> None:
        file, self._file, self._reader = self._file, None, None
        if file is not None:
            file.close()


__all__ = ["CSVObservationSource", "CSVSourceError"]
