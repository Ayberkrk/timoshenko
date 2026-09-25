"""Bounded-memory event-time monitoring sessions for caller-supplied streams."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Any, Sequence

import numpy as np

from .health import HealthAssessment, assess
from .modal import ModalResult, identify
from .multichannel import MultiChannelData
from .observations import ObservationBatch
from .oma import FDDResult, identify_fdd
from .sensors import SensorData
from .storage import SQLiteStore
from .structure import Structure
from .update import update


@dataclass(frozen=True)
class SessionReport:
    sequence: int
    event_time_s: float
    method: str
    structure: Structure
    modal: ModalResult | FDDResult
    health: HealthAssessment

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "event_time_s": self.event_time_s,
            "method": self.method,
            "structure": {
                "structure_id": self.structure.structure_id,
                "natural_frequencies_hz": list(self.structure.natural_frequencies_hz),
                "reference_frequencies_hz": list(self.structure.baseline_frequencies_hz),
                "update_status": self.structure.update_status,
            },
            "modal": self.modal.to_dict(),
            "health": self.health.to_dict(),
        }


@dataclass(frozen=True)
class SessionIngestResult:
    accepted_count: int
    rejected_quality_count: int
    unknown_sensor_count: int
    missing_timestamp_count: int
    invalid_time_count: int
    out_of_order_count: int
    unit_mismatch_count: int
    duplicate_batch: bool
    reports: tuple[SessionReport, ...]

    @property
    def status(self) -> str:
        return "analyzed" if self.reports else "buffering"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "accepted_count": self.accepted_count,
            "rejected_quality_count": self.rejected_quality_count,
            "unknown_sensor_count": self.unknown_sensor_count,
            "missing_timestamp_count": self.missing_timestamp_count,
            "invalid_time_count": self.invalid_time_count,
            "out_of_order_count": self.out_of_order_count,
            "unit_mismatch_count": self.unit_mismatch_count,
            "duplicate_batch": self.duplicate_batch,
            "reports": [report.to_dict() for report in self.reports],
        }


@dataclass(frozen=True)
class SessionRestoreResult:
    restored_samples: int
    samples_per_sensor: int
    ready_for_analysis: bool
    last_event_time_s: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "restored_samples": self.restored_samples,
            "samples_per_sensor": self.samples_per_sensor,
            "ready_for_analysis": self.ready_for_analysis,
            "last_event_time_s": self.last_event_time_s,
        }


class MonitoringSession:
    """Analyze regularly sampled point observations in bounded rolling windows.

    The host supplies observations; this class does not connect to a broker.
    Each sensor timestamp is mapped to the nearest sample grid point and must
    fall within ``timestamp_tolerance_s``. Late/duplicate sensor points are
    counted and excluded from the active buffer. If a sample is missing, the
    session waits until a new contiguous full window is available; it never
    interpolates or bridges a gap.
    """

    def __init__(
        self,
        structure: Structure,
        *,
        sensor_ids: Sequence[str],
        units: Sequence[str],
        sampling_hz: float,
        window_samples: int,
        hop_samples: int | None = None,
        timestamp_tolerance_s: float | None = None,
        analysis_options: dict[str, Any] | None = None,
        store: SQLiteStore | None = None,
    ):
        if not isinstance(structure, Structure):
            raise TypeError("structure must be a timoshenko.Structure")
        ids = tuple(str(value).strip() for value in sensor_ids)
        unit_values = tuple(str(value).strip() for value in units)
        hz = float(sampling_hz)
        window = int(window_samples)
        hop = max(1, window // 4) if hop_samples is None else int(hop_samples)
        tolerance = 0.25 / hz if timestamp_tolerance_s is None and math.isfinite(hz) and hz > 0 else float(timestamp_tolerance_s or 0.0)
        if not ids or len(ids) > 32 or any(not value for value in ids) or len(set(ids)) != len(ids):
            raise ValueError("sensor_ids must contain 1–32 distinct, non-empty ids")
        if len(unit_values) != len(ids) or any(not value for value in unit_values):
            raise ValueError("units must contain one non-empty unit per sensor")
        if len(ids) > 1 and len(set(unit_values)) != 1:
            raise ValueError("FDD monitoring requires every channel to use the same measurement unit")
        if not math.isfinite(hz) or hz <= 0.0:
            raise ValueError("sampling_hz must be finite and positive")
        if window < 16 or window > 65_536:
            raise ValueError("window_samples must be between 16 and 65536")
        if hop < 1 or hop > window:
            raise ValueError("hop_samples must be between 1 and window_samples")
        if not math.isfinite(tolerance) or tolerance < 0.0 or tolerance >= 0.5 / hz:
            raise ValueError("timestamp_tolerance_s must be finite, non-negative, and less than half a sample interval")
        if store is not None and not isinstance(store, SQLiteStore):
            raise TypeError("store must be a SQLiteStore or None")

        self._structure = structure
        self._sensor_ids = ids
        self._units = unit_values
        self._sampling_hz = hz
        self._window_samples = window
        self._hop_samples = hop
        self._timestamp_tolerance_s = tolerance
        self._options = dict(analysis_options or {})
        allowed = (
            {"max_modes", "min_frequency_hz", "max_frequency_hz", "min_peak_ratio"}
            if len(ids) == 1
            else {
                "nperseg", "overlap", "max_modes", "max_singular_values",
                "min_frequency_hz", "max_frequency_hz", "min_peak_ratio",
                "min_singular_value_ratio",
            }
        )
        unexpected = set(self._options) - allowed
        if unexpected:
            raise ValueError(f"unsupported analysis option(s) for this session: {', '.join(sorted(unexpected))}")
        self._store = store
        self._buffers = {sensor_id: deque(maxlen=window) for sensor_id in ids}
        self._last_key: dict[str, int] = {}
        self._seen_by_key: dict[int, set[str]] = {}
        self._last_analysis_key: int | None = None
        self._sequence = 0

    @property
    def structure(self) -> Structure:
        return self._structure

    @property
    def buffered_samples_by_sensor(self) -> dict[str, int]:
        return {sensor_id: len(buffer) for sensor_id, buffer in self._buffers.items()}

    def restore(self, *, extra_history_samples: int = 64) -> SessionRestoreResult:
        """Restore the newest common contiguous window from the configured store.

        The stored structure/model definition remains the caller's input; this
        method restores observation buffers and stream cursors only. It never
        re-appends restored observations or reruns an old analysis report.
        """
        if self._store is None:
            raise RuntimeError("restore requires a SQLiteStore configured on this session")
        extra = int(extra_history_samples)
        if extra < 0 or extra > 4096:
            raise ValueError("extra_history_samples must be between 0 and 4096")
        candidate_limit = min(self._window_samples + extra, 262_144)
        values_by_sensor: dict[str, dict[int, float]] = {}
        last_keys: dict[str, int] = {}
        for sensor_id, unit in zip(self._sensor_ids, self._units):
            samples: dict[int, float] = {}
            recent = self._store.recent_observations(
                sensor_id=sensor_id,
                unit=unit,
                limit=candidate_limit,
            )
            for observation in recent:
                if observation.timestamp is None:
                    continue
                key = int(round(observation.timestamp * self._sampling_hz))
                grid_time = key / self._sampling_hz
                if abs(observation.timestamp - grid_time) > self._timestamp_tolerance_s:
                    continue
                samples.setdefault(key, observation.value)
            values_by_sensor[sensor_id] = samples
            if samples:
                last_keys[sensor_id] = max(samples)

        common = set.intersection(*(set(samples) for samples in values_by_sensor.values()))
        common_keys = sorted(common)
        contiguous: list[int] = []
        if common_keys:
            contiguous = [common_keys[-1]]
            for key in reversed(common_keys[:-1]):
                if contiguous[-1] - key != 1:
                    break
                contiguous.append(key)
            contiguous.reverse()
        restored_keys = contiguous[-self._window_samples :]
        self._seen_by_key.clear()
        for sensor_id, buffer in self._buffers.items():
            buffer.clear()
            values = values_by_sensor[sensor_id]
            for key in restored_keys:
                buffer.append((key, values[key]))
        for key in restored_keys:
            self._seen_by_key[key] = set(self._sensor_ids)
        self._last_key = last_keys
        self._last_analysis_key = restored_keys[-1] if len(restored_keys) >= self._window_samples else None
        last_time = None if not restored_keys else restored_keys[-1] / self._sampling_hz
        return SessionRestoreResult(
            restored_samples=len(restored_keys) * len(self._sensor_ids),
            samples_per_sensor=len(restored_keys),
            ready_for_analysis=len(restored_keys) >= self._window_samples,
            last_event_time_s=last_time,
        )

    def ingest(self, batch: ObservationBatch) -> SessionIngestResult:
        if not isinstance(batch, ObservationBatch):
            raise TypeError("batch must be an ObservationBatch")
        duplicate_batch = False
        if self._store is not None:
            receipt = self._store.append_batch(batch)
            if receipt.was_duplicate:
                return SessionIngestResult(0, 0, 0, 0, 0, 0, 0, True, ())
            duplicate_batch = receipt.was_duplicate

        accepted = rejected_quality = unknown = missing_time = invalid_time = out_of_order = unit_mismatch = 0
        reports: list[SessionReport] = []
        index_by_sensor = {sensor_id: idx for idx, sensor_id in enumerate(self._sensor_ids)}
        for observation in batch.observations:
            idx = index_by_sensor.get(observation.sensor_id)
            if idx is None:
                unknown += 1
                continue
            if not observation.quality:
                rejected_quality += 1
                continue
            if observation.timestamp is None:
                missing_time += 1
                continue
            if observation.unit != self._units[idx]:
                unit_mismatch += 1
                continue
            key = int(round(observation.timestamp * self._sampling_hz))
            grid_time = key / self._sampling_hz
            if abs(observation.timestamp - grid_time) > self._timestamp_tolerance_s:
                invalid_time += 1
                continue
            previous = self._last_key.get(observation.sensor_id)
            if previous is not None and key <= previous:
                out_of_order += 1
                continue
            self._last_key[observation.sensor_id] = key
            self._buffers[observation.sensor_id].append((key, observation.value))
            self._seen_by_key.setdefault(key, set()).add(observation.sensor_id)
            accepted += 1
            if len(self._seen_by_key[key]) == len(self._sensor_ids):
                report = self._maybe_analyze(key)
                if report is not None:
                    reports.append(report)
            cutoff = key - 2 * self._window_samples
            for old_key in tuple(self._seen_by_key):
                if old_key < cutoff:
                    del self._seen_by_key[old_key]

        return SessionIngestResult(accepted, rejected_quality, unknown, missing_time, invalid_time, out_of_order, unit_mismatch, duplicate_batch, tuple(reports))

    def _latest_contiguous_window(self) -> tuple[list[int], np.ndarray] | None:
        values_by_sensor = {
            sensor_id: {key: value for key, value in buffer}
            for sensor_id, buffer in self._buffers.items()
        }
        common = set.intersection(*(set(values) for values in values_by_sensor.values()))
        if not common:
            return None
        keys = sorted(common)
        run: list[int] = [keys[-1]]
        for key in reversed(keys[:-1]):
            if run[-1] - key != 1:
                break
            run.append(key)
        run.reverse()
        if len(run) < self._window_samples:
            return None
        selected = run[-self._window_samples :]
        matrix = np.asarray(
            [[values_by_sensor[sensor_id][key] for sensor_id in self._sensor_ids] for key in selected],
            dtype=float,
        )
        return selected, matrix

    def _maybe_analyze(self, completed_key: int) -> SessionReport | None:
        if self._last_analysis_key is not None and completed_key - self._last_analysis_key < self._hop_samples:
            return None
        snapshot = self._latest_contiguous_window()
        if snapshot is None:
            return None
        keys, matrix = snapshot
        if len(self._sensor_ids) == 1:
            observations: SensorData | MultiChannelData = SensorData(
                samples=matrix[:, 0],
                sampling_hz=self._sampling_hz,
                unit=self._units[0],
                channel=self._sensor_ids[0],
            )
            modal = identify(observations, **self._options)
            method = "peak_picking"
        else:
            observations = MultiChannelData(
                samples=matrix,
                sampling_hz=self._sampling_hz,
                channel_ids=self._sensor_ids,
                units=self._units,
            )
            modal = identify_fdd(observations, **self._options)
            method = "fdd"
        if modal.modes:
            self._structure = update(self._structure, modal)
        health = assess(structure=self._structure, observations=observations, modal_result=modal)
        self._sequence += 1
        self._last_analysis_key = keys[-1]
        return SessionReport(
            sequence=self._sequence,
            event_time_s=keys[-1] / self._sampling_hz,
            method=method,
            structure=self._structure,
            modal=modal,
            health=health,
        )
