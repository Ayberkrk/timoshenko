"""Small local SQLite asset, observation, and analysis history store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import hashlib
import math
from pathlib import Path
import sqlite3
from typing import Any, Literal
import uuid

from .assets import Asset, Relation
from .observations import Observation, ObservationBatch
from .project import ProjectRunResult


_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise ValueError(f"value is not JSON-serializable: {error}") from None


@dataclass(frozen=True)
class BatchAppendResult:
    batch_id: str
    source_id: str
    inserted_count: int
    duplicate_count: int
    duplicate_batch: bool

    @property
    def was_duplicate(self) -> bool:
        return self.duplicate_batch


class SQLiteStore:
    """A one-process local history store backed by Python's SQLite module.

    Batch ingestion is idempotent for the unique ``(source_id, batch_id)``
    pair. Observations retain arrival order and timestamps as supplied. Reads
    can choose arrival or event-time order; this class does not interpolate,
    delete late values, or infer missing values.
    """

    def __init__(self, path: str | Path, *, timeout_seconds: float = 5.0):
        self.path = str(path)
        if self.path != ":memory:":
            db_path = Path(self.path).expanduser().resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.path = str(db_path)
        timeout = float(timeout_seconds)
        if not math.isfinite(timeout) or timeout <= 0.0:
            raise ValueError("timeout_seconds must be finite and positive")
        self._connection = sqlite3.connect(self.path, timeout=timeout)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._initialize()

    def _initialize(self) -> None:
        version = int(self._connection.execute("PRAGMA user_version").fetchone()[0])
        if version > _SCHEMA_VERSION:
            self.close()
            raise RuntimeError(f"database schema {version} is newer than supported schema {_SCHEMA_VERSION}")
        if version == _SCHEMA_VERSION:
            return
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS relations (
                    source_asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    relation_type TEXT NOT NULL,
                    target_asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (source_asset_id, relation_type, target_asset_id)
                );
                CREATE TABLE IF NOT EXISTS observation_batches (
                    source_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    item_count INTEGER NOT NULL,
                    batch_digest TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    PRIMARY KEY (source_id, batch_id)
                );
                CREATE TABLE IF NOT EXISTS observations (
                    observation_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    record_index INTEGER NOT NULL,
                    sensor_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    value REAL NOT NULL,
                    event_timestamp REAL,
                    quality INTEGER NOT NULL,
                    asset_id TEXT,
                    observation_source_id TEXT,
                    metadata_json TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    UNIQUE (source_id, batch_id, record_index)
                );
                CREATE INDEX IF NOT EXISTS observations_sensor_event_idx
                    ON observations (sensor_id, event_timestamp, observation_row_id);
                CREATE INDEX IF NOT EXISTS observations_asset_event_idx
                    ON observations (asset_id, event_timestamp, observation_row_id);
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    run_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    method TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    manifest_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
                PRAGMA user_version = 1;
                """
            )

    def close(self) -> None:
        if getattr(self, "_connection", None) is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> "SQLiteStore":
        if self._connection is None:
            raise RuntimeError("store is closed")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def upsert_asset(self, asset: Asset) -> None:
        if not isinstance(asset, Asset):
            raise TypeError("asset must be an Asset")
        with self._connection:
            self._connection.execute(
                """INSERT INTO assets(asset_id, asset_type, name, metadata_json, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(asset_id) DO UPDATE SET asset_type=excluded.asset_type,
                     name=excluded.name, metadata_json=excluded.metadata_json, updated_at=excluded.updated_at""",
                (asset.asset_id, asset.asset_type, asset.name, _json(asset.metadata), _utc_now()),
            )

    def get_asset(self, asset_id: str) -> Asset | None:
        row = self._connection.execute("SELECT * FROM assets WHERE asset_id=?", (str(asset_id),)).fetchone()
        if row is None:
            return None
        return Asset(row["asset_id"], row["asset_type"], row["name"], json.loads(row["metadata_json"]))

    def list_assets(self, *, asset_type: str | None = None) -> tuple[Asset, ...]:
        if asset_type is None:
            rows = self._connection.execute("SELECT * FROM assets ORDER BY asset_id").fetchall()
        else:
            rows = self._connection.execute("SELECT * FROM assets WHERE asset_type=? ORDER BY asset_id", (asset_type,)).fetchall()
        return tuple(Asset(row["asset_id"], row["asset_type"], row["name"], json.loads(row["metadata_json"])) for row in rows)

    def add_relation(self, relation: Relation) -> None:
        if not isinstance(relation, Relation):
            raise TypeError("relation must be a Relation")
        with self._connection:
            self._connection.execute(
                """INSERT INTO relations(source_asset_id, relation_type, target_asset_id, metadata_json)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(source_asset_id, relation_type, target_asset_id)
                   DO UPDATE SET metadata_json=excluded.metadata_json""",
                (relation.source_asset_id, relation.relation_type, relation.target_asset_id, _json(relation.metadata)),
            )

    def relations_for(self, asset_id: str) -> tuple[Relation, ...]:
        rows = self._connection.execute(
            "SELECT * FROM relations WHERE source_asset_id=? OR target_asset_id=? ORDER BY relation_type, source_asset_id, target_asset_id",
            (str(asset_id), str(asset_id)),
        ).fetchall()
        return tuple(Relation(row["source_asset_id"], row["relation_type"], row["target_asset_id"], json.loads(row["metadata_json"])) for row in rows)

    def append_batch(self, batch: ObservationBatch) -> BatchAppendResult:
        if not isinstance(batch, ObservationBatch):
            raise TypeError("batch must be an ObservationBatch")
        if not batch.batch_id.strip() or not batch.source_id.strip():
            raise ValueError("batch_id and source_id are required for idempotent persistence")
        serialized = _json([item.to_dict() for item in batch.observations])
        batch_digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        inserted = 0
        with self._connection:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO observation_batches(source_id, batch_id, item_count, batch_digest, received_at) VALUES (?, ?, ?, ?, ?)",
                (batch.source_id, batch.batch_id, batch.count, batch_digest, _utc_now()),
            )
            is_new = cursor.rowcount == 1
            if not is_new:
                existing = self._connection.execute(
                    "SELECT batch_digest FROM observation_batches WHERE source_id=? AND batch_id=?",
                    (batch.source_id, batch.batch_id),
                ).fetchone()
                if existing is None or existing["batch_digest"] != batch_digest:
                    raise ValueError("batch_id was already stored with different observation content")
            if is_new:
                for record_index, observation in enumerate(batch.observations):
                    self._connection.execute(
                        """INSERT INTO observations(
                            source_id, batch_id, record_index, sensor_id, name, unit, value,
                            event_timestamp, quality, asset_id, observation_source_id, metadata_json, ingested_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            batch.source_id,
                            batch.batch_id,
                            record_index,
                            observation.sensor_id,
                            observation.name,
                            observation.unit,
                            observation.value,
                            observation.timestamp,
                            int(observation.quality),
                            observation.asset_id,
                            observation.source_id or batch.source_id,
                            _json(observation.metadata),
                            _utc_now(),
                        ),
                    )
                    inserted += 1
        duplicate = 0 if is_new else batch.count
        return BatchAppendResult(batch.batch_id, batch.source_id, inserted, duplicate, not is_new)

    def observations(
        self,
        *,
        sensor_id: str | None = None,
        asset_id: str | None = None,
        start_timestamp: float | None = None,
        end_timestamp: float | None = None,
        order_by: Literal["event_time", "arrival"] = "event_time",
        limit: int | None = None,
    ) -> tuple[Observation, ...]:
        if order_by not in {"event_time", "arrival"}:
            raise ValueError("order_by must be 'event_time' or 'arrival'")
        clauses: list[str] = []
        parameters: list[Any] = []
        if sensor_id is not None:
            clauses.append("sensor_id=?")
            parameters.append(str(sensor_id))
        if asset_id is not None:
            clauses.append("asset_id=?")
            parameters.append(str(asset_id))
        if start_timestamp is not None:
            start = float(start_timestamp)
            if not math.isfinite(start):
                raise ValueError("start_timestamp must be finite")
            clauses.append("event_timestamp>=?")
            parameters.append(start)
        if end_timestamp is not None:
            end = float(end_timestamp)
            if not math.isfinite(end):
                raise ValueError("end_timestamp must be finite")
            clauses.append("event_timestamp<=?")
            parameters.append(end)
        if start_timestamp is not None and end_timestamp is not None and start > end:
            raise ValueError("start_timestamp must be less than or equal to end_timestamp")
        ordering = "event_timestamp IS NULL, event_timestamp, observation_row_id" if order_by == "event_time" else "observation_row_id"
        sql = "SELECT * FROM observations" + (" WHERE " + " AND ".join(clauses) if clauses else "") + " ORDER BY " + ordering
        if limit is not None:
            if int(limit) < 1:
                raise ValueError("limit must be positive")
            sql += " LIMIT ?"
            parameters.append(int(limit))
        rows = self._connection.execute(sql, parameters).fetchall()
        return tuple(
            Observation(
                sensor_id=row["sensor_id"],
                name=row["name"],
                unit=row["unit"],
                value=row["value"],
                timestamp=row["event_timestamp"],
                quality=bool(row["quality"]),
                asset_id=row["asset_id"],
                source_id=row["observation_source_id"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        )

    def save_run(self, result: ProjectRunResult, *, run_id: str | None = None) -> str:
        if not isinstance(result, ProjectRunResult):
            raise TypeError("result must be a ProjectRunResult")
        identifier = str(run_id or uuid.uuid4()).strip()
        if not identifier:
            raise ValueError("run_id must be non-empty")
        with self._connection:
            self._connection.execute(
                """INSERT INTO analysis_runs(
                     run_id, project_id, method, source_sha256, manifest_sha256, created_at, result_json
                   ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    identifier,
                    result.project_id,
                    result.method,
                    result.source_sha256,
                    result.manifest_sha256,
                    _utc_now(),
                    _json(result.to_dict()),
                ),
            )
        return identifier

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self._connection.execute("SELECT result_json FROM analysis_runs WHERE run_id=?", (str(run_id),)).fetchone()
        return None if row is None else json.loads(row["result_json"])

    def list_runs(self, *, project_id: str | None = None, limit: int = 100) -> tuple[dict[str, Any], ...]:
        if int(limit) < 1:
            raise ValueError("limit must be positive")
        if project_id is None:
            rows = self._connection.execute("SELECT result_json FROM analysis_runs ORDER BY created_at DESC, run_id DESC LIMIT ?", (int(limit),)).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT result_json FROM analysis_runs WHERE project_id=? ORDER BY created_at DESC, run_id DESC LIMIT ?",
                (str(project_id), int(limit)),
            ).fetchall()
        return tuple(json.loads(row["result_json"]) for row in rows)
