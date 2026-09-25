import re
import subprocess
import sys
from pathlib import Path

import pytest

import timoshenko as tm

ROOT = Path(__file__).resolve().parents[1]


def test_version_matches_package_metadata():
    declared = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.MULTILINE).group(1)
    assert tm.__version__ == declared


def test_storage_does_not_import_the_analysis_stack():
    # Importing a submodule normally runs the package __init__, which imports
    # everything; a stub package isolates the submodule's own imports.
    probe = (
        "import sys, types\n"
        f"pkg = types.ModuleType('timoshenko'); pkg.__path__ = [{str(ROOT / 'src' / 'timoshenko')!r}]\n"
        "sys.modules['timoshenko'] = pkg\n"
        "import timoshenko.storage\n"
        "print('timoshenko.project' in sys.modules, 'timoshenko.health' in sys.modules)\n"
    )
    completed = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert completed.stdout.split() == ["False", "False"]


def test_closed_store_reports_that_it_is_closed():
    store = tm.SQLiteStore(":memory:")
    store.close()
    with pytest.raises(RuntimeError, match="closed"):
        store.list_assets()
    store.close()


def test_sensorthings_wraps_numeric_overflow():
    from timoshenko.sensorthings import SensorThingsSourceError

    body = ('{"value":[{"phenomenonTime":"2024-01-01T00:00:00Z","result":1' + "0" * 400 + "}]}").encode()
    source = tm.SensorThingsObservationSource(
        "https://sta.example.org/Observations", sensor_id="s", unit="g", fetcher=lambda request, timeout, limit: body
    )
    source.open()
    with pytest.raises(SensorThingsSourceError):
        source.read_batch()


def test_formula_modules_share_validation_messages():
    for call in (lambda: tm.rectangle_section(0.0, 1.0), lambda: tm.axial_stress(1.0, -1.0),
                 lambda: tm.cantilever_tip_load(1.0, 0.0, 1.0, 1.0), lambda: tm.natural_frequency_hz(float("nan"), 1.0)):
        with pytest.raises(ValueError, match="must be finite and greater than zero"):
            call()
