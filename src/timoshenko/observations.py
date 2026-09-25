"""Generic point-observation records shared by adapters and asset workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Observation:
    """One sensor value with event time, unit, quality, and provenance metadata.

    ``timestamp`` is Unix time in seconds. It may be ``None`` for a
    non-temporal snapshot; streaming adapters should preserve device event
    time separately from ingestion/arrival time in ``metadata``.
    """

    sensor_id: str
    name: str
    unit: str
    value: float
    timestamp: float | None = None
    quality: bool = True
    asset_id: str | None = None
    source_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        sensor_id, name, unit = (str(item).strip() for item in (self.sensor_id, self.name, self.unit))
        value = float(self.value)
        timestamp = None if self.timestamp is None else float(self.timestamp)
        if not sensor_id or not name or not unit:
            raise ValueError("sensor_id, name, and unit must be non-empty")
        if not math.isfinite(value):
            raise ValueError("observation value must be finite")
        if timestamp is not None and not math.isfinite(timestamp):
            raise ValueError("timestamp must be finite or None")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a mapping")
        object.__setattr__(self, "sensor_id", sensor_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "timestamp", timestamp)
        object.__setattr__(self, "quality", bool(self.quality))
        object.__setattr__(self, "asset_id", None if self.asset_id is None else str(self.asset_id))
        object.__setattr__(self, "source_id", None if self.source_id is None else str(self.source_id))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "name": self.name,
            "unit": self.unit,
            "value": self.value,
            "timestamp": self.timestamp,
            "quality": self.quality,
            "asset_id": self.asset_id,
            "source_id": self.source_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ObservationBatch:
    """A batch in arrival order; consumers choose event-time sorting policy."""

    observations: Sequence[Observation]
    batch_id: str = ""
    source_id: str = ""

    def __post_init__(self) -> None:
        items = tuple(self.observations)
        if any(not isinstance(item, Observation) for item in items):
            raise TypeError("observations must contain only Observation objects")
        object.__setattr__(self, "observations", items)
        object.__setattr__(self, "batch_id", str(self.batch_id).strip())
        object.__setattr__(self, "source_id", str(self.source_id).strip())

    @property
    def count(self) -> int:
        return len(self.observations)

    def for_sensor(self, sensor_id: str) -> tuple[Observation, ...]:
        """Return matching records in original batch arrival order."""
        target = str(sensor_id)
        return tuple(item for item in self.observations if item.sensor_id == target)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "source_id": self.source_id,
            "count": self.count,
            "observations": [item.to_dict() for item in self.observations],
        }
