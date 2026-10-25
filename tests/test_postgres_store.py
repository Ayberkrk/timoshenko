"""Integration tests run by the PostgreSQL service in GitHub Actions."""

from __future__ import annotations

from importlib import import_module
import os
import uuid

import pytest

import timoshenko as tm
from timoshenko.postgres import PostgresStore
from timoshenko.storage import HistoryStore

POSTGRES_DSN = os.environ.get("TIMOSHENKO_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(
    not POSTGRES_DSN,
    reason="set TIMOSHENKO_POSTGRES_DSN to run PostgreSQL integration tests",
)


@pytest.fixture
def store():
    assert POSTGRES_DSN is not None
    schema = f"test_{uuid.uuid4().hex}"
    value = PostgresStore(POSTGRES_DSN, schema=schema)
    try:
        yield value
    finally:
        if value._connection is None:
            cleanup_connection = import_module("psycopg").connect(POSTGRES_DSN)
        else:
            cleanup_connection = value._db
        with cleanup_connection.cursor() as cursor:
            cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
        cleanup_connection.close()
        value.close()


def _batch(batch_id: str, value: float = 1.0) -> tm.ObservationBatch:
    return tm.ObservationBatch(
        [
            tm.Observation("sensor-a", "deck", "m/s^2", value, timestamp=10.0),
            tm.Observation("sensor-a", "deck", "m/s^2", value + 1.0, timestamp=11.0),
        ],
        source_id="gateway-a",
        batch_id=batch_id,
    )


def test_postgres_store_observation_idempotency_filtering_pruning_and_session(store):
    assert isinstance(store, HistoryStore)
    batch = _batch("batch-a")
    appended = store.append_batch(batch)
    replayed = store.append_batch(batch)
    assert appended.inserted_count == 2
    assert not appended.was_duplicate
    assert replayed.inserted_count == 0
    assert replayed.was_duplicate
    with pytest.raises(ValueError, match="different observation content"):
        store.append_batch(_batch("batch-a", value=5.0))

    observations = store.observations(sensor_id="sensor-a", start_timestamp=10.5)
    assert [item.value for item in observations] == [2.0]
    assert [item.value for item in store.recent_observations(sensor_id="sensor-a", limit=1)] == [
        2.0
    ]
    assert store.prune_before(10.5) == 1
    assert store.has_batch(batch)

    session = tm.MonitoringSession(
        tm.Structure([100_000.0], [20_000_000.0]),
        sensor_ids=["sensor-a"],
        units=["m/s^2"],
        sampling_hz=100.0,
        window_samples=16,
        store=store,
    )
    assert session.restore().restored_samples == 1


def test_postgres_store_assets_relations_and_foreign_key_rollback(store):
    store.upsert_asset(tm.Asset("bridge-1", "bridge", "Main span", {"year": 2020}))
    store.upsert_asset(tm.Asset("sensor-1", "sensor"))
    store.add_relation(tm.Relation("sensor-1", "mounted_on", "bridge-1"))
    assert store.get_asset("bridge-1").metadata == {"year": 2020}
    assert [asset.asset_id for asset in store.list_assets(asset_type="sensor")] == ["sensor-1"]
    assert len(store.relations_for("bridge-1")) == 1
    foreign_key_violation = import_module("psycopg.errors").ForeignKeyViolation
    with pytest.raises(foreign_key_violation):
        store.add_relation(tm.Relation("sensor-1", "mounted_on", "missing-asset"))
    assert len(store.relations_for("bridge-1")) == 1


def test_postgres_store_close_is_idempotent_and_guards_use(store):
    store.close()
    store.close()
    with pytest.raises(RuntimeError, match="closed"):
        store.observations()
