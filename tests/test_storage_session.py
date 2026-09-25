import math
import sqlite3

import numpy as np
import pytest

import timoshenko as tm


def batch(start, count, *, fs=100.0, frequency=7.0, sensors=("a",), batch_id="", source_id="", unit="g", skip=()):
    observations = []
    for index in range(start, start + count):
        if index in skip:
            continue
        for offset, sensor in enumerate(sensors):
            value = math.sin(2 * math.pi * frequency * index / fs) * (1.0 + 0.3 * offset)
            observations.append(tm.Observation(sensor, sensor, unit, value, timestamp=index / fs))
    return tm.ObservationBatch(observations, batch_id=batch_id, source_id=source_id)


def test_batch_append_is_idempotent_and_detects_changed_content(tmp_path):
    with tm.SQLiteStore(tmp_path / "h.db") as store:
        first = store.append_batch(batch(0, 10, batch_id="b1", source_id="s"))
        again = store.append_batch(batch(0, 10, batch_id="b1", source_id="s"))
        assert (first.inserted_count, first.was_duplicate) == (10, False)
        assert (again.inserted_count, again.was_duplicate) == (0, True)
        with pytest.raises(ValueError):
            store.append_batch(batch(0, 11, batch_id="b1", source_id="s"))
        with pytest.raises(ValueError):
            store.append_batch(batch(0, 3))
    with tm.SQLiteStore(tmp_path / "h.db") as reopened:
        assert len(reopened.observations(sensor_id="a")) == 10


def test_event_time_and_arrival_order(tmp_path):
    late = tm.Observation("a", "a", "g", 1.0, timestamp=5.0)
    early = tm.Observation("a", "a", "g", 2.0, timestamp=1.0)
    with tm.SQLiteStore(tmp_path / "h.db") as store:
        store.append_batch(tm.ObservationBatch([late, early], batch_id="b", source_id="s"))
        assert [o.value for o in store.observations(order_by="event_time")] == [2.0, 1.0]
        assert [o.value for o in store.observations(order_by="arrival")] == [1.0, 2.0]
        assert [o.value for o in store.recent_observations(sensor_id="a", limit=1)] == [1.0]


def test_assets_and_relations():
    with tm.SQLiteStore(":memory:") as store:
        store.upsert_asset(tm.Asset("bridge-1", "bridge", "Main span"))
        store.upsert_asset(tm.Asset("s-1", "sensor"))
        store.upsert_asset(tm.Asset("bridge-1", "bridge", "Renamed"))
        store.add_relation(tm.Relation("s-1", "mounted_on", "bridge-1"))
        assert store.get_asset("bridge-1").name == "Renamed"
        assert [a.asset_id for a in store.list_assets(asset_type="sensor")] == ["s-1"]
        assert len(store.relations_for("bridge-1")) == 1
        with pytest.raises(sqlite3.IntegrityError):
            store.add_relation(tm.Relation("s-1", "mounted_on", "missing"))


def test_newer_schema_is_refused(tmp_path):
    path = tmp_path / "future.db"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA user_version = 99")
    connection.close()
    with pytest.raises(RuntimeError):
        tm.SQLiteStore(path)


def make_session(**kwargs):
    defaults = dict(sensor_ids=["a"], units=["g"], sampling_hz=100.0, window_samples=256, hop_samples=128)
    defaults.update(kwargs)
    return tm.MonitoringSession(tm.Structure([1.0e5], [2.0e8]), **defaults)


def test_session_analyzes_every_hop_once_window_is_full():
    session = make_session()
    first = session.ingest(batch(0, 255))
    assert first.status == "buffering"
    second = session.ingest(batch(255, 1 + 128 * 2))
    assert [report.sequence for report in second.reports] == [1, 2, 3]
    assert second.reports[0].modal.frequencies_hz == pytest.approx([7.0], abs=100.0 / 256)


def test_session_gap_blocks_analysis_until_a_new_contiguous_window():
    session = make_session()
    result = session.ingest(batch(0, 400, skip={200}))
    assert result.reports == ()
    result = session.ingest(batch(400, 57))
    assert [r.event_time_s for r in result.reports] == pytest.approx([4.56])


def test_session_counts_rejected_observations():
    session = make_session()
    observations = [
        tm.Observation("a", "a", "g", 0.0, timestamp=1.0),
        tm.Observation("a", "a", "g", 0.0, timestamp=1.0),
        tm.Observation("a", "a", "m/s^2", 0.0, timestamp=1.01),
        tm.Observation("a", "a", "g", 0.0, timestamp=1.023),
        tm.Observation("a", "a", "g", 0.0, timestamp=None),
        tm.Observation("a", "a", "g", 0.0, timestamp=1.05, quality=False),
        tm.Observation("zz", "zz", "g", 0.0, timestamp=1.06),
    ]
    result = session.ingest(tm.ObservationBatch(observations))
    assert (result.accepted_count, result.out_of_order_count, result.unit_mismatch_count, result.invalid_time_count,
            result.missing_timestamp_count, result.rejected_quality_count, result.unknown_sensor_count) == (1, 1, 1, 1, 1, 1, 1)


def test_multichannel_session_uses_fdd():
    session = make_session(sensor_ids=["a", "b"], units=["g", "g"], window_samples=512, hop_samples=512,
                           analysis_options={"nperseg": 256})
    result = session.ingest(batch(0, 512, sensors=("a", "b")))
    assert [report.method for report in result.reports] == ["fdd"]
    assert result.reports[0].modal.frequencies_hz[0] == pytest.approx(7.0, abs=100.0 / 256)


def test_session_rejects_unknown_options_and_mixed_units():
    with pytest.raises(ValueError):
        make_session(analysis_options={"nperseg": 64})
    with pytest.raises(ValueError):
        make_session(sensor_ids=["a", "b"], units=["g", "m"])


def test_duplicate_batch_is_not_reanalyzed(tmp_path):
    with tm.SQLiteStore(tmp_path / "h.db") as store:
        session = make_session(store=store)
        first = session.ingest(batch(0, 256, batch_id="b1", source_id="s"))
        again = session.ingest(batch(0, 256, batch_id="b1", source_id="s"))
        assert len(first.reports) == 1
        assert again.duplicate_batch and again.reports == () and again.accepted_count == 0


def test_restore_rebuilds_latest_contiguous_window(tmp_path):
    path = tmp_path / "h.db"
    with tm.SQLiteStore(path) as store:
        session = make_session(store=store)
        session.ingest(batch(0, 300, batch_id="b1", source_id="s"))
    with tm.SQLiteStore(path) as store:
        session = make_session(store=store)
        restored = session.restore()
        assert restored.ready_for_analysis
        assert restored.samples_per_sensor == 256
        assert restored.last_event_time_s == pytest.approx(2.99)
        result = session.ingest(batch(300, 128, batch_id="b2", source_id="s"))
        assert len(result.reports) == 1
        stale = session.ingest(tm.ObservationBatch([tm.Observation("a", "a", "g", 0.0, timestamp=1.0)], batch_id="b3", source_id="s"))
        assert stale.out_of_order_count == 1


def test_restore_without_store_is_an_error():
    with pytest.raises(RuntimeError):
        make_session().restore()


def test_observation_validation():
    with pytest.raises(ValueError):
        tm.Observation("a", "a", "g", float("nan"))
    with pytest.raises(ValueError):
        tm.Observation("", "a", "g", 1.0)
    with pytest.raises(TypeError):
        tm.ObservationBatch([1.0])
    assert np.isfinite(tm.Observation("a", "a", "g", 1, timestamp=0).value)
