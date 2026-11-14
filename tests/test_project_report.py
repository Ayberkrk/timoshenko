import hashlib
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

import timoshenko as tm

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def write_project(tmp_path, channels=("acc",), options=None):
    fs, n = 100.0, 4096
    csv_path = tmp_path / "data.csv"
    header = ",".join(channels)
    rows = [
        ",".join(
            f"{math.sin(2 * math.pi * 6.0 * i / fs) * (1 + c):.9f}" for c in range(len(channels))
        )
        for i in range(n)
    ]
    csv_path.write_text(header + "\n" + "\n".join(rows) + "\n")
    manifest = {
        "schema_version": "1",
        "project": {"id": "p1", "name": "Demo <b>tower</b>"},
        "structure": {
            "type": "shear_building",
            "story_masses_kg": [1e5],
            "story_stiffness_n_m": [2e8],
        },
        "observations": {
            "file": "data.csv",
            "sampling_hz": fs,
            "channels": [{"column": c, "unit": "g"} for c in channels],
        },
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
        with pytest.raises(TypeError, match="result must be a ProjectRunResult"):
            store.save_run(object())
        with pytest.raises(ValueError, match="run_id must be non-empty"):
            store.save_run(result, run_id=" ")
        run_id = store.save_run(result, run_id="r1")
        assert store.get_run(run_id) == json.loads(json.dumps(result.to_dict()))
        assert store.get_run("missing") is None
        assert store.list_runs(project_id="p1") == (result.to_dict(),)
        assert store.list_runs(project_id="other") == ()
        with pytest.raises(ValueError, match="limit must be positive"):
            store.list_runs(limit=0)
        with pytest.raises(sqlite3.IntegrityError):
            store.save_run(result, run_id="r1")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda m: m.update(schema_version="2"), "unsupported schema_version"),
        (lambda m: m["structure"].update(type="frame"), "supports structure.type='shear_building'"),
        (
            lambda m: m["analysis"].update(options={"nperseg": 256}),
            "unsupported analysis options for peak_picking",
        ),
        (lambda m: m["analysis"].update(method="fdd"), "fdd requires at least two channels"),
        (
            lambda m: m["observations"].update(sampling_hz=0),
            "observations.sampling_hz must be a finite positive number",
        ),
    ],
    ids=["schema", "structure-type", "option-for-method", "fdd-one-channel", "sampling"],
)
def test_manifest_validation(tmp_path, mutate, message):
    path, _ = write_project(tmp_path)
    manifest = json.loads(path.read_text())
    mutate(manifest)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=message):
        tm.read_manifest(path)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda m: m.update(project=[]), r"project\.id must be a non-empty string"),
        (lambda m: m["project"].update(id=" \t"), r"project\.id must be a non-empty string"),
        (lambda m: m.update(observations=[]), "observations must be a JSON object"),
        (
            lambda m: m["observations"].update(file=" "),
            r"observations\.file must be a non-empty path",
        ),
        (lambda m: m["observations"].update(file="data.txt"), "support CSV observations"),
        (
            lambda m: m["observations"].pop("sampling_hz"),
            r"sampling_hz must be a finite positive number",
        ),
        (
            lambda m: m["observations"].update(channels=[]),
            r"observations\.channels must be a non-empty list",
        ),
        (
            lambda m: m["observations"].update(channels={}),
            r"observations\.channels must be a non-empty list",
        ),
        (
            lambda m: m["observations"].update(channels=["acc"]),
            r"observations\.channels\[0\] must be an object",
        ),
        (
            lambda m: m["observations"]["channels"][0].update(column=" "),
            r"channels\[0\] needs non-empty column, id, and unit",
        ),
        (
            lambda m: m["observations"]["channels"][0].update(id=" "),
            r"channels\[0\] needs non-empty column, id, and unit",
        ),
        (
            lambda m: m["observations"]["channels"][0].update(unit=" "),
            r"channels\[0\] needs non-empty column, id, and unit",
        ),
        (
            lambda m: m["observations"]["channels"].append({"column": "acc", "id": "other"}),
            "channel columns and ids must each be unique",
        ),
        (
            lambda m: m["observations"].update(
                channels=[{"column": "a", "id": "same"}, {"column": "b", "id": "same"}]
            ),
            "channel columns and ids must each be unique",
        ),
        (lambda m: m.update(analysis=[]), "analysis must be a JSON object"),
        (
            lambda m: m["analysis"].update(method="unknown"),
            r"analysis\.method must be 'peak_picking' or 'fdd'",
        ),
        (lambda m: m["analysis"].update(options=[]), r"analysis\.options must be a JSON object"),
    ],
    ids=[
        "project-object",
        "blank-project-id",
        "observations-object",
        "blank-file",
        "non-csv-file",
        "missing-sampling",
        "empty-channels",
        "channels-object",
        "channel-object",
        "blank-column",
        "blank-channel-id",
        "blank-unit",
        "duplicate-column",
        "duplicate-channel-id",
        "analysis-object",
        "unknown-method",
        "options-object",
    ],
)
def test_manifest_rejects_invalid_fields(tmp_path, mutate, message):
    path, _ = write_project(tmp_path)
    manifest = json.loads(path.read_text())
    mutate(manifest)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=message):
        tm.read_manifest(path)


@pytest.mark.parametrize("sampling_hz", [None, "invalid", "nan", "inf", "-inf", 0, -1])
def test_manifest_rejects_invalid_sampling_rate(tmp_path, sampling_hz):
    path, _ = write_project(tmp_path)
    manifest = json.loads(path.read_text())
    manifest["observations"]["sampling_hz"] = sampling_hz
    path.write_text(json.dumps(manifest))
    with pytest.raises(
        ValueError, match=r"observations\.sampling_hz must be a finite positive number"
    ):
        tm.read_manifest(path)


def test_manifest_rejects_non_json_extension(tmp_path):
    path = tmp_path / "project.txt"
    path.write_text("{}")
    with pytest.raises(ValueError, match=r"project manifests must use the \.json extension"):
        tm.read_manifest(path)


@pytest.mark.parametrize("payload", [[], None, "project", 1])
def test_manifest_rejects_non_object_root(tmp_path, payload):
    path = tmp_path / "project.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="project manifest root must be a JSON object"):
        tm.read_manifest(path)


def test_manifest_rejects_peak_picking_with_multiple_channels(tmp_path):
    path, _ = write_project(tmp_path, channels=("a", "b"))
    manifest = json.loads(path.read_text())
    manifest["analysis"]["method"] = "peak_picking"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="peak_picking requires exactly one channel; use fdd"):
        tm.read_manifest(path)


def test_load_project_rejects_missing_observation_file(tmp_path):
    path, _ = write_project(tmp_path)
    manifest = json.loads(path.read_text())
    manifest["observations"]["file"] = "missing.csv"
    path.write_text(json.dumps(manifest))
    with pytest.raises(FileNotFoundError, match=r"observation CSV not found: .*missing\.csv"):
        tm.load_project(path)


def test_run_project_rejects_invalid_input():
    with pytest.raises(
        TypeError,
        match=r"project must be a manifest path or LoadedProject from tm\.load_project\(\)",
    ):
        tm.run_project(object())


def test_report_escapes_user_text_and_lists_limits(tmp_path):
    manifest, _ = write_project(tmp_path)
    result = tm.run_project(manifest)
    html = tm.report.to_html(result)
    assert "<b>tower</b>" not in html and "&lt;b&gt;tower&lt;/b&gt;" in html
    assert "not a diagnosis of damage" in html
    saved = tm.report.save_html(result, tmp_path / "out" / "report.html")
    assert saved.read_text(encoding="utf-8") == html


def test_report_handles_result_without_modes():
    html = tm.report.to_html(
        tm.monitor(tm.Structure([1e5], [2e8]), tm.SensorData([0.0] * 64, 10.0))
    )
    assert "No usable modal frequencies" in html


EXAMPLES_WITH_OWN_TEST = {"replay_csv.py", "pynite_shear_beam.py"}


@pytest.mark.parametrize(
    "script", sorted(p.name for p in EXAMPLES.glob("*.py") if p.name not in EXAMPLES_WITH_OWN_TEST)
)
def test_examples_run(script, tmp_path):
    completed = subprocess.run(
        [sys.executable, str(EXAMPLES / script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr


def test_replay_csv_example(tmp_path):
    path = tmp_path / "obs.csv"
    lines = ["timestamp,sensor_id,name,unit,value,quality,asset_id"]
    lines += [f"{i / 100.0},a,a,g,{math.sin(2 * math.pi * 5 * i / 100.0)},1," for i in range(600)]
    path.write_text("\n".join(lines) + "\n")
    completed = subprocess.run(
        [
            sys.executable,
            str(EXAMPLES / "replay_csv.py"),
            str(path),
            "--sensor-id",
            "a",
            "--unit",
            "g",
            "--sample-rate",
            "100",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr


def test_pynite_example(tmp_path):
    pynite = pytest.importorskip("Pynite")
    import inspect

    if "shear_deformable" not in inspect.signature(pynite.FEModel3D.add_member).parameters:
        pytest.skip("installed PyNite has no shear-deformable members")
    completed = subprocess.run(
        [sys.executable, str(EXAMPLES / "pynite_shear_beam.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
