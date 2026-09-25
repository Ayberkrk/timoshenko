import json
import math
from types import SimpleNamespace

import pytest

import timoshenko as tm
from timoshenko.csv_source import CSVSourceError
from timoshenko.sensorthings import SensorThingsSourceError


def session(window=64, **kwargs):
    return tm.MonitoringSession(tm.Structure([1.0e5], [2.0e8]), sensor_ids=["a"], units=["g"],
                                sampling_hz=100.0, window_samples=window, hop_samples=window, **kwargs)


def write_long_csv(path, rows=40):
    lines = ["timestamp,sensor_id,name,unit,value,quality,asset_id"]
    for index in range(rows):
        lines.append(f"{index / 100.0},a,acc,g,{math.sin(index / 2.0)},good,")
    path.write_text("\n".join(lines) + "\n")


def test_csv_source_batches_with_stable_ids(tmp_path):
    path = tmp_path / "obs.csv"
    write_long_csv(path)
    source = tm.CSVObservationSource(path, batch_size=16)
    ids = []
    for _ in range(2):
        source.open()
        batches = []
        while (item := source.read_batch()) is not None:
            batches.append(item)
        source.close()
        ids.append([b.batch_id for b in batches])
        assert [b.count for b in batches] == [16, 16, 8]
    assert ids[0] == ids[1] == ["csv:obs.csv:rows:1-16", "csv:obs.csv:rows:17-32", "csv:obs.csv:rows:33-40"]


@pytest.mark.parametrize(
    "row, message",
    [
        ("2024-01-01T00:00:00,a,acc,g,1.0,good,", "timezone"),
        ("0.1,a,acc,g,abc,good,", "invalid observation"),
        ("0.1,a,acc,g,1.0,maybe,", "quality"),
        ("0.1,a,acc,g,1.0,good,,extra", "more fields"),
    ],
)
def test_csv_source_rejects_bad_rows(tmp_path, row, message):
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,sensor_id,name,unit,value,quality,asset_id\n" + row + "\n")
    source = tm.CSVObservationSource(path)
    source.open()
    with pytest.raises(CSVSourceError, match=message):
        source.read_batch()
    source.close()


def test_csv_source_accepts_zulu_iso_timestamps(tmp_path):
    path = tmp_path / "iso.csv"
    path.write_text("timestamp,sensor_id,unit,value\n2024-01-01T00:00:00Z,a,g,1.5\n")
    source = tm.CSVObservationSource(path, name_column=None, quality_column=None, asset_id_column=None)
    source.open()
    item = source.read_batch().observations[0]
    assert item.timestamp == 1704067200.0 and item.name == "a"
    source.close()


class ListSource:
    def __init__(self, batches, fail_at=None):
        self.batches, self.fail_at = list(batches), fail_at
        self.opened = self.closed = 0
        self.acked = []

    def open(self):
        self.opened += 1

    def read_batch(self):
        if self.fail_at is not None and not self.batches[: self.fail_at]:
            raise OSError("link down")
        return self.batches.pop(0) if self.batches else None

    def close(self):
        self.closed += 1

    def acknowledge(self, batch, result):
        self.acked.append(batch.batch_id)


def obs_batch(start, count, batch_id):
    return tm.ObservationBatch(
        [tm.Observation("a", "a", "g", math.sin(i), timestamp=i / 100.0) for i in range(start, start + count)],
        batch_id=batch_id, source_id="src",
    )


def test_runner_ingests_acknowledges_and_closes():
    source = ListSource([obs_batch(0, 32, "b1"), obs_batch(32, 32, "b2")])
    with tm.SessionRunner(source, session()) as runner:
        results = list(runner)
    assert [r.accepted_count for r in results] == [32, 32]
    assert results[-1].status == "analyzed"
    assert source.acked == ["b1", "b2"]
    assert (source.opened, source.closed) == (1, 1)


def test_runner_closes_source_on_read_error_and_early_exit():
    failing = ListSource([], fail_at=0)
    with pytest.raises(OSError):
        with tm.SessionRunner(failing, session()) as runner:
            list(runner)
    assert failing.closed == 1
    partial = ListSource([obs_batch(0, 8, "b1"), obs_batch(8, 8, "b2")])
    with tm.SessionRunner(partial, session(), max_batches=1) as runner:
        assert len(list(runner)) == 1
    assert partial.closed == 1 and partial.batches


def test_runner_requires_context_manager():
    runner = tm.SessionRunner(ListSource([]), session())
    with pytest.raises(RuntimeError):
        list(runner)


class GoodPlugin:
    name = "demo"
    api_version = tm.PLUGIN_API_VERSION

    def register(self, registry):
        registry.register_source("list", lambda **config: ListSource([]))


def test_plugin_registry_contract():
    registry = tm.PluginRegistry()
    registry.register(GoodPlugin())
    assert registry.source_names == ("list",)
    assert isinstance(registry.create_source("LIST"), ListSource)
    with pytest.raises(tm.PluginError):
        registry.register(GoodPlugin())
    old = GoodPlugin()
    old.name, old.api_version = "old", "0"
    with pytest.raises(tm.PluginCompatibilityError):
        registry.register(old)
    clash = GoodPlugin()
    clash.name = "clash"
    with pytest.raises(tm.PluginError):
        registry.register(clash)
    with pytest.raises(KeyError):
        registry.create_source("missing")


def test_failed_plugin_registration_is_not_partially_visible():
    class Partial(GoodPlugin):
        name = "partial"

        def register(self, registry):
            registry.register_source("first", lambda: None)
            raise RuntimeError("boom")

    registry = tm.PluginRegistry()
    with pytest.raises(tm.PluginLoadError):
        registry.register(Partial())
    assert registry.source_names == () and registry.installed_plugins == ()


def test_installed_entry_points_load():
    registry = tm.PluginRegistry.load_entry_points()
    assert {"mqtt", "sensorthings"} <= set(registry.source_names)


class FakePaho:
    def __init__(self, backlog=()):
        self.acks, self.subscriptions = [], []
        self.on_connect = self.on_message = None
        self.backlog = list(backlog)

    def username_pw_set(self, username, password):
        self.credentials = (username, password)

    def tls_set(self):
        self.tls = True

    def connect(self, host, port, keepalive):
        return 0

    def loop_start(self):
        self.on_connect(self, None, {}, 0, None)
        for args, kwargs in self.backlog:
            self.deliver(*args, **kwargs)

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def subscribe(self, topic, qos):
        self.subscriptions.append((topic, qos))
        return 0, 1

    def ack(self, mid, qos):
        self.acks.append(mid)
        return 0

    def deliver(self, mid, payload, *, retain=False, qos=1):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.on_message(self, None, SimpleNamespace(mid=mid, qos=qos, retain=retain, payload=body))


def mqtt_payload(batch_id, start, count):
    return {
        "schema_version": 1,
        "source_id": "gateway",
        "batch_id": batch_id,
        "observations": [
            {"sensor_id": "a", "name": "a", "unit": "g", "value": math.sin(i), "timestamp": i / 100.0}
            for i in range(start, start + count)
        ],
    }


def test_mqtt_acknowledges_after_ingest_and_skips_retained():
    client = FakePaho(backlog=[
        ((1, mqtt_payload("old", 0, 4)), {"retain": True}),
        ((2, mqtt_payload("b1", 0, 32)), {}),
        ((3, mqtt_payload("b2", 32, 32)), {}),
    ])
    source = tm.MqttObservationSource(host="broker", topic="site/acc", client_id="c1", client_factory=lambda: client)
    acks_seen_during_ingest = []

    class Watching(tm.MonitoringSession):
        def ingest(self, batch):
            acks_seen_during_ingest.append(list(client.acks))
            return super().ingest(batch)

    watched = Watching(tm.Structure([1e5], [2e8]), sensor_ids=["a"], units=["g"], sampling_hz=100.0, window_samples=64)
    with tm.SessionRunner(source, watched, max_batches=2) as runner:
        results = list(runner)
    assert client.subscriptions == [("site/acc", 1)]
    assert source.retained_drop_count == 1
    assert [r.accepted_count for r in results] == [32, 32]
    assert acks_seen_during_ingest == [[1], [1, 2]]
    assert client.acks == [1, 2, 3]


@pytest.mark.parametrize(
    "payload",
    [b"not json", {"schema_version": 2, "source_id": "g", "batch_id": "b", "observations": [{}]},
     {"schema_version": 1, "source_id": "g", "batch_id": "b", "observations": [{"sensor_id": "a", "name": "a", "unit": "g", "value": 1}]}],
    ids=["garbage", "schema", "no-timestamp"],
)
def test_mqtt_invalid_payload_surfaces_as_error(payload):
    client = FakePaho()
    source = tm.MqttObservationSource(host="broker", topic="t", client_id="c", client_factory=lambda: client)
    source.open()
    client.deliver(1, payload)
    with pytest.raises(tm.MQTTSourceError):
        source.read_batch()
    source.close()


def test_mqtt_queue_overflow_is_not_silent():
    client = FakePaho()
    source = tm.MqttObservationSource(host="b", topic="t", client_id="c", queue_capacity=1, client_factory=lambda: client)
    source.open()
    client.deliver(1, mqtt_payload("b1", 0, 2))
    client.deliver(2, mqtt_payload("b2", 2, 2))
    # Fail fast: the queued, unacknowledged b1 is left for broker redelivery.
    with pytest.raises(tm.MQTTSourceError, match="queue is full"):
        source.read_batch()
    assert client.acks == []


def test_mqtt_configuration_validation():
    with pytest.raises(ValueError):
        tm.MqttObservationSource(host="b", topic="site/#", client_id="c")
    with pytest.raises(ValueError):
        tm.MqttObservationSource(host="b", topic="t")
    with pytest.raises(ValueError):
        tm.MqttObservationSource(host="b", topic="t", client_id="c", password="x")


def sensorthings_page(start, count, next_link=None):
    document = {"value": [
        {"@iot.id": i, "phenomenonTime": f"2024-01-01T00:00:{i:02d}Z", "result": float(i), "parameters": {"ok": i != 3}}
        for i in range(start, start + count)
    ]}
    if next_link:
        document["@iot.nextLink"] = next_link
    return json.dumps(document).encode()


def test_sensorthings_follows_same_origin_pagination_opaquely():
    base = "https://sta.example.org/v1.1/Datastreams(7)/Observations"
    next_url = "https://sta.example.org/v1.1/Datastreams(7)/Observations?$skip=5&$top=5&weird=%20"
    pages = {base: sensorthings_page(0, 5, next_url), next_url: sensorthings_page(5, 5)}
    requested = []

    def fetch(request, timeout, limit):
        requested.append((request.full_url, request.get_header("Authorization")))
        return pages[request.full_url]

    source = tm.SensorThingsObservationSource(base, sensor_id="s", unit="g", bearer_token="t0k",
                                              quality_parameter="ok", fetcher=fetch)
    source.open()
    first, second, end = source.read_batch(), source.read_batch(), source.read_batch()
    assert end is None
    assert [url for url, _ in requested] == [base, next_url]
    assert all(auth == "Bearer t0k" for _, auth in requested)
    assert [o.quality for o in first.observations] == [True, True, True, False, True]
    assert second.observations[0].timestamp == 1704067205.0
    assert first.batch_id != second.batch_id


def test_sensorthings_rejects_cross_origin_next_link_and_bad_results():
    base = "https://sta.example.org/Observations"
    source = tm.SensorThingsObservationSource(
        base, sensor_id="s", unit="g", default_quality=True,
        fetcher=lambda request, timeout, limit: sensorthings_page(0, 1, "https://evil.example.com/next"),
    )
    source.open()
    with pytest.raises(SensorThingsSourceError, match="origin"):
        source.read_batch()
    bad = tm.SensorThingsObservationSource(
        base, sensor_id="s", unit="g",
        fetcher=lambda request, timeout, limit: json.dumps({"value": [{"phenomenonTime": "2024-01-01T00:00:00Z", "result": "7"}]}).encode(),
    )
    bad.open()
    with pytest.raises(SensorThingsSourceError, match="scalar"):
        bad.read_batch()


def test_sensorthings_quality_defaults_to_unknown_false():
    source = tm.SensorThingsObservationSource(
        "https://sta.example.org/Observations", sensor_id="s", unit="g",
        fetcher=lambda request, timeout, limit: sensorthings_page(0, 2),
    )
    source.open()
    assert [o.quality for o in source.read_batch().observations] == [False, False]
