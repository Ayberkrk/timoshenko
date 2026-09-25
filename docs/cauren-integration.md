# Cauren interoperability

## Boundary

Timoshenko owns reusable, domain-independent calculations. Cauren owns bridge/civil schemas, sensor-name and unit interpretation, calibrated risk thresholds, model routing, and engineering review language. An FDD or modal-frequency output is evidence, not a Cauren risk decision.

The repository's `cauren_physics.timoshenko_adapter` is an optional bridge. When the separately installed `timoshenko` package is importable, Cauren delegates its generic single-channel modal identification and lumped-mass shear-building natural-frequency calculation to the library. When it is unavailable, Cauren keeps its pure-Python fallback so the root package still has no required third-party dependency. Existing public Cauren result objects, method strings, confidence/power scaling, and baseline comparison thresholds are kept at the boundary.

## Local use

From the repository root:

```bash
python -m pip install -e ./Timoshenko
```

Then existing Cauren calls can transparently share the generic engine work:

```python
from cauren_physics.fe_reference_model import ShearBuildingModel, natural_frequencies_hz
from cauren_physics.oma import identify_modal_parameters

building = ShearBuildingModel((50_000.0,), (8_000_000.0,))
theoretical_hz = natural_frequencies_hz(building)
observed = identify_modal_parameters(acceleration_samples, sampling_hz=100.0)
```

Without installation, the same calls remain on the dependency-free Cauren implementation. This integration is optional and does not yet remove the fallback implementation. The next migration step is to measure the behavior over Cauren's established modal examples, then decide whether a supported Timoshenko package extra/release should become a maintained dependency.

## Compatibility checks performed

The bridge was exercised with Timoshenko source/wheel paths and with no Timoshenko import path. On a deterministic two-frequency input, the delegated Cauren output preserved peak frequency, half-power damping, power-scaled amplitude, confidence, result method string, and frequency resolution relative to the legacy implementation. The fallback path also remained callable without the engine. This is a targeted smoke comparison, not the full Cauren test suite.

Since the audit fixes, damping is no longer numerically identical between the two paths. Timoshenko now estimates damping from an averaged spectrum and withholds it when the half-power bandwidth is not resolved, while Cauren's fallback still uses the single-periodogram estimate. Frequencies, amplitudes, confidence and resolution are unchanged. Cauren's OMA damping is informational (its risk path uses frequency drift), and aligning the fallback is a Cauren-side change.
