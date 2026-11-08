"""Run every script in examples/ so an API change cannot break them silently.

The README code blocks already run in tests/test_package.py; this file gives
the standalone examples the same treatment. Each example runs in a subprocess
with its working directory set to a temporary folder, so scripts that write
files stay self-contained. Pynite is an optional dependency: its example is
skipped with a stated reason when it is not installed.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
TIMEOUT_SECONDS = 300

# Examples needing an optional extra are skipped (not failed) without it.
OPTIONAL_DEPENDENCIES = {"pynite_shear_beam.py": "Pynite"}


def _csv_for_replay(tmp_path: Path) -> Path:
    # Columns follow CSVObservationSource's defaults: timestamp (Unix seconds),
    # sensor_id, unit, value.
    path = tmp_path / "observations.csv"
    rows = ["timestamp,sensor_id,unit,value,name,quality,asset_id"]
    for index in range(2048):
        timestamp = 1_800_000_000.0 + index / 100.0
        value = 0.5 * (index % 64) / 64.0
        rows.append(f"{timestamp:.3f},deck-left,m/s^2,{value:.6f},deck-accel,good,demo-bridge")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def _arguments_for(name: str, tmp_path: Path) -> list[str]:
    if name == "replay_csv.py":
        return [
            str(_csv_for_replay(tmp_path)),
            "--sensor-id",
            "deck-left",
            "--unit",
            "m/s^2",
            "--sample-rate",
            "100.0",
        ]
    return []


@pytest.mark.parametrize(
    "name",
    sorted(path.name for path in EXAMPLES.glob("*.py")),
)
def test_example_script_runs_cleanly(name: str, tmp_path: Path):
    optional = OPTIONAL_DEPENDENCIES.get(name)
    if optional is not None:
        pytest.importorskip(optional, reason=f"{name} needs the optional dependency {optional}")
    completed = subprocess.run(
        [sys.executable, str(EXAMPLES / name), *_arguments_for(name, tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    assert completed.returncode == 0, (
        f"{name} exited {completed.returncode}\n"
        f"--- stdout (tail) ---\n{completed.stdout[-2000:]}\n"
        f"--- stderr (tail) ---\n{completed.stderr[-2000:]}"
    )
