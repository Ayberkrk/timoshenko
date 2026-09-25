import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

import timoshenko as tm

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def write_project(tmp_path, channels=("acc",), options=None):
    fs, n = 100.0, 4096
    csv_path = tmp_path / "data.csv"
    header = ",".join(channels)
    rows = [",".join(f"{math.sin(2 * math.pi * 6.0 * i / fs) * (1 + c):.9f}" for c in range(len(channels))) for i in range(n)]
    csv_path.write_text(header + "\n" + "\n".join(rows) + "\n")
    manifest = {
        "schema_version": "1",
        "project": {"id": "p1", "name": "Demo <b>tower</b>"},
        "structure": {"type": "shear_building", "story_masses_kg": [1e5], "story_stiffness_n_m": [2e8]},
        "observations": {"file": "data.csv", "sampling_hz": fs,
                         "channels": [{"column": c, "unit": "g"} for c in channels]},
        "analysis": {"options": options or {}},
    }
    path = tmp_path / "project.json"
    path.write_text(json.dumps(manifest))
    return path, csv_path


def test_project_run_is_deterministic_and_records_provenance(tmp_path):
    manifest, data = write_project(tmp_path)
    first, second = tm.run_project(manifest), tm.run_project(tm.load_project(manifest))
    assert first.to_dict() == second.to_dict()
    assert first.method == "peak_picking"
    assert first.source_sha256 == hashlib.sha256(data.read_bytes()).hexdigest()
    assert first.manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
    json.dumps(first.to_dict(), allow_nan=False)


def test_project_multichannel_uses_fdd_and_can_be_stored(tmp_path):
    manifest, _ = write_project(tmp_path, channels=("a", "b"), options={"nperseg": 512})
    result = tm.run_project(manifest)
    assert result.method == "fdd"
    with tm.SQLiteStore(tmp_path / "runs.db") as store:
        run_id = store.save_run(result, run_id="r1")
        assert store.get_run(run_id) == json.loads(json.dumps(result.to_dict()))
        with pytest.raises(Exception):
            store.save_run(result, run_id="r1")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.update(schema_version="2"),
        lambda m: m["structure"].update(type="frame"),
        lambda m: m["analysis"].update(options={"nperseg": 256}),
        lambda m: m["analysis"].update(method="fdd"),
        lambda m: m["observations"].update(sampling_hz=0),
    ],
    ids=["schema", "structure-type", "option-for-method", "fdd-one-channel", "sampling"],
)
def test_manifest_validation(tmp_path, mutate):
    path, _ = write_project(tmp_path)
    manifest = json.loads(path.read_text())
    mutate(manifest)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        tm.read_manifest(path)


def test_report_escapes_user_text_and_lists_limits(tmp_path):
    manifest, _ = write_project(tmp_path)
    result = tm.run_project(manifest)
    html = tm.report.to_html(result)
    assert "<b>tower</b>" not in html and "&lt;b&gt;tower&lt;/b&gt;" in html
    assert "not a diagnosis of damage" in html
    saved = tm.report.save_html(result, tmp_path / "out" / "report.html")
    assert saved.read_text(encoding="utf-8") == html


def test_report_handles_result_without_modes():
    html = tm.report.to_html(tm.monitor(tm.Structure([1e5], [2e8]), tm.SensorData([0.0] * 64, 10.0)))
    assert "No usable modal frequencies" in html


@pytest.mark.parametrize("script", sorted(p.name for p in EXAMPLES.glob("*.py") if p.name != "replay_csv.py"))
def test_examples_run(script, tmp_path):
    completed = subprocess.run([sys.executable, str(EXAMPLES / script)], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr


def test_replay_csv_example(tmp_path):
    path = tmp_path / "obs.csv"
    lines = ["timestamp,sensor_id,name,unit,value,quality,asset_id"]
    lines += [f"{i / 100.0},a,a,g,{math.sin(2 * math.pi * 5 * i / 100.0)},1," for i in range(600)]
    path.write_text("\n".join(lines) + "\n")
    completed = subprocess.run(
        [sys.executable, str(EXAMPLES / "replay_csv.py"), str(path), "--sensor-id", "a", "--unit", "g", "--sample-rate", "100"],
        capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
