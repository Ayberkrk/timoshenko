"""Confirmed defects, recorded as strict expected failures.

Each test states the correct behavior. When a defect is fixed its test starts
passing, ``strict=True`` turns that into a failure, and the marker must be
removed in the same change.
"""

import math
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

import timoshenko as tm


def defect(reason):
    return pytest.mark.xfail(strict=True, reason=reason)


@defect("load_sensors drops blank CSV cells, shortening a regularly sampled record and shifting later samples in time")
def test_load_sensors_rejects_blank_values(tmp_path):
    path = tmp_path / "gappy.csv"
    path.write_text("value\n" + "".join(("" if 30 <= i < 40 else f"{math.sin(i)}") + "\n" for i in range(100)))
    with pytest.raises(ValueError):
        tm.load_sensors(path, sampling_hz=100.0)


@defect("half-power bandwidth of a Hann-windowed periodogram is reported as damping even when it is only window leakage")
def test_undamped_sine_is_not_reported_as_damped():
    t = np.arange(1000) / 100.0
    mode = tm.modal.identify(tm.SensorData(np.sin(2 * np.pi * 5.0 * t), 100.0)).modes[0]
    assert mode.damping_ratio is None or mode.damping_ratio < 1e-3


@defect("half-power on a single raw periodogram of ambient response underestimates 2% damping by more than an order of magnitude")
def test_ambient_damping_is_within_a_factor_of_two_or_withheld():
    fs, fn, zeta = 50.0, 2.0, 0.02
    wn, dt = 2 * math.pi * fn, 1 / fs
    force = np.random.default_rng(0).standard_normal(int(600 * fs))
    x = v = 0.0
    response = np.empty_like(force)
    for i, f in enumerate(force):
        for _ in range(10):
            v += (f - 2 * zeta * wn * v - wn * wn * x) * dt / 10
            x += v * dt / 10
        response[i] = x
    estimate = tm.modal.identify(tm.SensorData(response, fs), max_modes=1).modes[0].damping_ratio
    assert estimate is None or zeta / 2 <= estimate <= zeta * 2


@defect("update/health pair modes by index, so a mode missed at a sensor node is compared with the wrong analytical mode")
def test_missed_mode_does_not_invent_stiffness_change():
    structure = tm.Structure([1e5] * 3, [2e8] * 3)
    f1, _, f3 = structure.natural_frequencies_hz
    t = np.arange(20000) / 100.0
    signal = np.sin(2 * np.pi * f1 * t) + 0.5 * np.sin(2 * np.pi * f3 * t)
    result = tm.monitor(structure, tm.SensorData(signal, 100.0))
    assert result.structure.update_scale_factor == pytest.approx(1.0, abs=0.05)
    assert all(abs(change.change_pct) < 2.0 for change in result.health.mode_changes)


@defect("review_recommended fires on any negative change, so FFT bin quantization flags an unchanged structure about half the time")
def test_unchanged_structure_is_not_flagged_by_bin_quantization():
    structure = tm.Structure([1e5], [2e8])
    f0 = structure.natural_frequencies_hz[0]
    flagged = 0
    for n in range(4000, 4100):
        t = np.arange(n) / 100.0
        health = tm.health.assess(structure=structure, observations=tm.SensorData(np.sin(2 * np.pi * f0 * t), 100.0))
        flagged += health.review_recommended
    assert flagged <= 5


@defect("analysis option values are validated only when the first window is analyzed, not when the session is created")
def test_invalid_analysis_option_values_fail_at_construction():
    with pytest.raises(ValueError):
        tm.MonitoringSession(tm.Structure([1e5], [2e8]), sensor_ids=["a"], units=["g"], sampling_hz=100.0,
                             window_samples=64, analysis_options={"max_frequency_hz": 0.5})


@defect("ingest persists the batch before processing it; a mid-batch failure strands persisted samples that redelivery then skips as duplicate")
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
        session = tm.MonitoringSession(tm.Structure([1e5], [2e8]), sensor_ids=["a"], units=["g"], sampling_hz=100.0,
                                       window_samples=64, hop_samples=64, store=store)
        batch = tm.ObservationBatch(
            [tm.Observation("a", "a", "g", math.sin(i / 3), timestamp=i / 100.0) for i in range(128)],
            batch_id="b1", source_id="src",
        )
        with pytest.raises(RuntimeError):
            session.ingest(batch)
        session.ingest(batch)
        assert session._buffers["a"][-1][0] == 127


@defect("MonitoringSession re-updates the already updated model, so update_scale_factor becomes relative to the previous window")
def test_session_scale_factor_stays_relative_to_original_model():
    structure = tm.Structure([1e5], [2e8])
    f_damaged = structure.natural_frequencies_hz[0] * math.sqrt(0.9)
    session = tm.MonitoringSession(structure, sensor_ids=["a"], units=["g"], sampling_hz=100.0,
                                   window_samples=2048, hop_samples=2048)
    batch = tm.ObservationBatch([
        tm.Observation("a", "a", "g", math.sin(2 * math.pi * f_damaged * i / 100.0), timestamp=i / 100.0)
        for i in range(4096)
    ])
    reports = session.ingest(batch).reports
    assert [round(r.structure.update_scale_factor, 2) for r in reports] == [0.9, 0.9]


@defect("urllib follows HTTP redirects and forwards the bearer token to another origin; only @iot.nextLink is origin-checked")
def test_sensorthings_does_not_send_token_to_redirect_target():
    seen = {}

    class Other(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["authorization"] = self.headers.get("Authorization")
            body = b'{"value": []}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    other = HTTPServer(("127.0.0.1", 0), Other)

    class Redirect(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{other.server_port}/collect")
            self.end_headers()

        def log_message(self, format, *args):
            pass

    configured = HTTPServer(("127.0.0.1", 0), Redirect)
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in (other, configured)]
    for thread in threads:
        thread.start()
    try:
        source = tm.SensorThingsObservationSource(
            f"http://127.0.0.1:{configured.server_port}/Observations", sensor_id="s", unit="g", bearer_token="secret"
        )
        source.open()
        try:
            source.read_batch()
        except Exception:
            pass
        assert seen.get("authorization") is None
    finally:
        other.shutdown()
        configured.shutdown()
