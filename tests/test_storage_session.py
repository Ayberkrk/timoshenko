import math
import sqlite3

import numpy as np
import pytest

import timoshenko as tm


def batch(
    start,
    count,
    *,
    fs=100.0,
    frequency=7.0,
    sensors=("a",),
    batch_id="",
    source_id="",
    unit="g",
    skip=(),
):
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
    defaults = dict(
        sensor_ids=["a"], units=["g"], sampling_hz=100.0, window_samples=256, hop_samples=128
    )
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
    assert (
        result.accepted_count,
        result.out_of_order_count,
        result.unit_mismatch_count,
        result.invalid_time_count,
        result.missing_timestamp_count,
        result.rejected_quality_count,
        result.unknown_sensor_count,
    ) == (1, 1, 1, 1, 1, 1, 1)


def test_multichannel_session_uses_fdd():
    session = make_session(
        sensor_ids=["a", "b"],
        units=["g", "g"],
        window_samples=512,
        hop_samples=512,
        analysis_options={"nperseg": 256},
    )
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
        stale = session.ingest(
            tm.ObservationBatch(
                [tm.Observation("a", "a", "g", 0.0, timestamp=1.0)], batch_id="b3", source_id="s"
            )
        )
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


def test_has_batch_is_read_only_and_detects_conflicts(tmp_path):
    with tm.SQLiteStore(tmp_path / "h.db") as store:
        first = batch(0, 4, batch_id="b1", source_id="s")
        assert not store.has_batch(first)
        assert not store.has_batch(first)
        store.append_batch(first)
        assert store.has_batch(first)
        with pytest.raises(ValueError):
            store.has_batch(batch(0, 5, batch_id="b1", source_id="s"))


def test_invalid_analysis_option_values_fail_at_construction():
    with pytest.raises(ValueError):
        make_session(analysis_options={"max_frequency_hz": 0.1})
    with pytest.raises(ValueError):
        make_session(sensor_ids=["a", "b"], units=["g", "g"], analysis_options={"nperseg": 256})
    with pytest.raises(ValueError):
        make_session(review_threshold_pct=-1.0)


def test_redelivered_batch_after_mid_batch_failure_reaches_the_session(tmp_path, monkeypatch):
    real_identify = tm.session.identify
    calls = {"count": 0}

    def fail_once(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient analysis failure")
        return real_identify(*args, **kwargs)

    monkeypatch.setattr(tm.session, "identify", fail_once)
    with tm.SQLiteStore(tmp_path / "h.db") as store:
        session = make_session(window_samples=64, hop_samples=64, store=store)
        delivery = batch(0, 128, batch_id="b1", source_id="s")
        with pytest.raises(RuntimeError):
            session.ingest(delivery)
        assert store.observations(sensor_id="a") == ()
        retry = session.ingest(delivery)
        assert session._buffers["a"][-1][0] == 127
        assert retry.out_of_order_count == 64 and retry.accepted_count == 64
        assert len(store.observations(sensor_id="a")) == 128
        assert session.ingest(delivery).duplicate_batch


def test_session_scale_factor_stays_relative_to_original_model():
    structure = tm.Structure([1e5], [2e8])
    frequency = structure.natural_frequencies_hz[0] * math.sqrt(0.9)
    session = make_session(window_samples=2048, hop_samples=2048)
    reports = session.ingest(batch(0, 4096, frequency=frequency)).reports
    assert [round(r.structure.update_scale_factor, 2) for r in reports] == [0.9, 0.9]
    assert session.structure.story_stiffness_n_m[0] == pytest.approx(
        2e8 * reports[-1].structure.update_scale_factor
    )


def test_session_review_threshold_reaches_health():
    structure = tm.Structure([1e5], [2e8])
    frequency = structure.natural_frequencies_hz[0] * 0.8
    session = make_session(window_samples=2048, hop_samples=2048, review_threshold_pct=5.0)
    report = session.ingest(batch(0, 2048, frequency=frequency)).reports[0]
    assert report.health.review_recommended


def test_ingest_cost_does_not_grow_with_window_size():
    import time

    session = make_session(window_samples=65536, hop_samples=65536)
    session.ingest(batch(0, 60000, frequency=3.0))
    start = time.perf_counter()
    session.ingest(batch(60000, 4000, frequency=3.0))
    assert time.perf_counter() - start < 2.0


@pytest.mark.parametrize("timeout", [0, -1, math.nan, math.inf])
def test_store_rejects_non_positive_or_non_finite_timeout(timeout, tmp_path):
    with pytest.raises(ValueError, match="timeout_seconds must be finite and positive"):
        tm.SQLiteStore(tmp_path / "invalid.db", timeout_seconds=timeout)


def test_store_rejects_wrong_types_and_non_json_asset_metadata(tmp_path):
    with tm.SQLiteStore(tmp_path / "history.db") as store:
        with pytest.raises(TypeError, match="batch must be an ObservationBatch"):
            store.append_batch(object())
        with pytest.raises(TypeError, match="asset must be an Asset"):
            store.upsert_asset(object())
        with pytest.raises(TypeError, match="relation must be a Relation"):
            store.add_relation(object())
        with pytest.raises(ValueError, match="value is not JSON-serializable"):
            store.upsert_asset(tm.Asset("bad", "sensor", metadata={"value": object()}))


def test_store_closed_state_is_reported_by_context_and_queries():
    store = tm.SQLiteStore(":memory:")
    store.close()
    with pytest.raises(RuntimeError, match="store is closed"):
        store.__enter__()
    with pytest.raises(RuntimeError, match="SQLiteStore is closed"):
        store.get_asset("missing")


def test_store_filters_observations_by_asset_and_time_and_returns_missing_assets():
    records = [
        tm.Observation("a", "deck", "mm", 1.0, timestamp=1.0, asset_id="deck-1"),
        tm.Observation("a", "deck", "mm", 2.0, timestamp=2.0, asset_id="deck-1"),
        tm.Observation("a", "deck", "mm", 3.0, timestamp=3.0, asset_id="deck-2"),
        tm.Observation("b", "pier", "mm", 4.0, timestamp=2.0, asset_id="deck-1"),
    ]
    with tm.SQLiteStore(":memory:") as store:
        store.append_batch(tm.ObservationBatch(records, batch_id="filter", source_id="source"))
        selected = store.observations(
            sensor_id="a", asset_id="deck-1", start_timestamp=1.0, end_timestamp=2.0, limit=2
        )
        assert [(item.value, item.asset_id) for item in selected] == [
            (1.0, "deck-1"),
            (2.0, "deck-1"),
        ]
        limited = store.observations(sensor_id="a", asset_id="deck-1", limit=1)
        assert [item.value for item in limited] == [1.0]
        assert store.get_asset("missing") is None
        assert store.list_assets(asset_type="missing") == ()


@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"order_by": "newest"}, "order_by must be"),
        ({"start_timestamp": math.nan}, "start_timestamp must be finite"),
        ({"end_timestamp": math.inf}, "end_timestamp must be finite"),
        (
            {"start_timestamp": 2.0, "end_timestamp": 1.0},
            "start_timestamp must be less than or equal",
        ),
        ({"limit": 0}, "limit must be positive"),
    ],
)
def test_observation_query_rejects_invalid_order_bounds_and_limit(arguments, message):
    with tm.SQLiteStore(":memory:") as store, pytest.raises(ValueError, match=message):
        store.observations(**arguments)


@pytest.mark.parametrize("limit", [0, -1, 262145])
def test_recent_observations_rejects_limits_outside_supported_range(limit):
    with (
        tm.SQLiteStore(":memory:") as store,
        pytest.raises(ValueError, match="limit must be between 1 and 262144"),
    ):
        store.recent_observations(sensor_id="a", limit=limit)


def test_recent_observations_include_only_timestamped_good_values_matching_unit():
    records = [
        tm.Observation("a", "a", "g", 1.0, timestamp=1.0),
        tm.Observation("a", "a", "g", 2.0, timestamp=2.0, quality=False),
        tm.Observation("a", "a", "g", 3.0, timestamp=None),
        tm.Observation("a", "a", "m/s^2", 4.0, timestamp=4.0),
        tm.Observation("a", "a", "g", 5.0, timestamp=5.0),
    ]
    with tm.SQLiteStore(":memory:") as store:
        store.append_batch(tm.ObservationBatch(records, batch_id="recent", source_id="source"))
        recent = store.recent_observations(sensor_id="a", limit=1, unit="g")
        assert [(item.value, item.timestamp, item.quality) for item in recent] == [(5.0, 5.0, True)]
