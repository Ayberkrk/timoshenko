<p align="center">
  <img src="https://raw.githubusercontent.com/Ayberkrk/timoshenko/main/assets/timoshenko-logo.png" alt="Timoshenko Engine logo" width="920">
</p>

<h1 align="center">Timoshenko Engine</h1>

<p align="center">
  Reusable structural engineering building blocks for Python applications.
</p>

<p align="center">
  <img alt="Version 2.0.1" src="https://img.shields.io/badge/version-2.0.1-orange?style=for-the-badge">
  <img alt="Alpha" src="https://img.shields.io/badge/stage-alpha-orange?style=for-the-badge">
  <img alt="Python 3.10 to 3.13" src="https://img.shields.io/badge/python-3.10%20to%203.13-blue?style=for-the-badge">
  <img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache--2.0-green?style=for-the-badge">
  <a href="https://github.com/Ayberkrk/timoshenko/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/Ayberkrk/timoshenko/actions/workflows/tests.yml/badge.svg"></a>
</p>

Timoshenko packages common structural calculations, modal analysis, sensor
workflows, and monitoring components so applications can reuse them instead
of rebuilding the same foundations for every project. It is an embeddable
Python library and engine core, not a hosted monitoring service or a general
finite-element solver.

> **Alpha:** the API may still change between releases. Timoshenko is not yet
> published on PyPI; install it from GitHub or from a checkout as shown below.

## Install

From GitHub:

```bash
python -m pip install "timoshenko-engine @ git+https://github.com/Ayberkrk/timoshenko"
```

Or from the root of a checkout:

```bash
python -m pip install .
```

The distribution package is named `timoshenko-engine`. The Python import
package is named `timoshenko`:

```python
import timoshenko as tm
print(tm.__version__)
```

To install optional MQTT support, use:

```bash
python -m pip install '.[mqtt]'
```

A future published release can be installed with
`python -m pip install timoshenko-engine`. That command is only usable after a
release is available from the selected package index.

## Quick start

```python
import timoshenko as tm

structure = tm.Structure(
    structure_id="building-01",
    story_masses_kg=[120_000.0, 110_000.0],
    story_stiffness_n_m=[85_000_000.0, 70_000_000.0],
)

sensors = tm.load_sensors(
    "acceleration.csv",
    sampling_hz=100.0,
    column="acceleration_m_s2",
    unit="m/s^2",
)

modal = tm.modal.identify(sensors)
updated = tm.update(structure, modal)
health = tm.health.assess(structure=updated, observations=sensors)

print(health.to_dict())
```

For a one-shot pipeline, `tm.monitor(structure, sensors)` performs the same
analysis sequence and returns a serializable result. The model update applies
one global stiffness multiplier and keeps the analytical reference frequencies
separate from measured frequencies.

## What it provides

| Area | Reusable components |
|---|---|
| Structural models | Lumped-mass shear-building models and analytical natural frequencies |
| Modal analysis | Single-channel peak picking, damping estimates when resolvable, and multi-channel FDD with complex mode shapes |
| Model comparison | Log-frequency mode pairing, global stiffness updating, and evidence-oriented health assessment |
| Monitoring | Caller-fed bounded sessions, batch validation, source adapters, and optional plugins |
| Data workflow | Sensor CSV loading, project manifests, local SQLite history, and CSV replay |
| Reporting | Standalone HTML reports with an embedded SVG frequency comparison |
| Engineering calculations | Beam cases, section properties, mechanics, vibration, stability, stress, pressure, torsion, and uncertainty helpers |

Timoshenko can be used module by module or embedded in a larger product such as
Cauren. Sensor collection, application-specific risk rules, and engineering
interpretation remain with the integrating application.

## Multi-channel modal screening

FDD requires synchronized channels with a common sample rate and unit:

```python
signals = tm.load_multichannel_csv(
    "aligned_accelerometers.csv",
    columns=["deck_left", "deck_center", "deck_right"],
    sampling_hz=100.0,
    units=["m/s^2"] * 3,
)
fdd = tm.identify_fdd(signals, nperseg=1024, max_modes=5)
print(fdd.to_dict())
```

This first FDD implementation returns candidate frequencies and complex mode
shapes. It does not estimate damping or issue a damage or safety conclusion.

## Bounded monitoring session

A caller supplies timestamped observation batches. The session aligns samples,
waits for a fresh contiguous analysis window after gaps, and emits reports after
each configured hop:

```python
session = tm.MonitoringSession(
    structure,
    sensor_ids=["deck-left", "deck-right"],
    units=["m/s^2", "m/s^2"],
    sampling_hz=100.0,
    window_samples=2048,
    hop_samples=512,
    analysis_options={"nperseg": 512, "max_modes": 4},
)
result = session.ingest(batch)
for report in result.reports:
    tm.report.save_html(report, "reports/latest.html")
```

A gateway remains responsible for collecting data and handling transport
reconnection. Timoshenko does not run a background collector or select an alarm
policy.

## Further examples and documentation

- [Documentation home](docs/index.md)
- [Architecture](docs/architecture.md)
- [Data contract](docs/data-contract.md)
- [Historical CSV replay](docs/csv-source.md)
- [Plugin contract](docs/plugin-contract.md)
- [Rayleigh damping](docs/rayleigh-damping.md)
- [Section properties](docs/section-properties.md)
- [Polygon section properties](docs/polygon-sections.md)
- [Equation uncertainty](docs/uncertainty.md)
- [Numerical methods and limits](docs/numerical-methods.md)
- [Monitoring sessions](docs/live-sessions.md)
- [Source adapters](docs/adapters.md)
- [Project manifests](docs/project-manifest.md)
- [Local storage](docs/storage.md)
- [Reports](docs/reporting.md)
- [Optional MQTT adapter](docs/mqtt-adapter.md)
- [SensorThings adapter](docs/sensorthings-adapter.md)
- [Engineering calculations](examples/engineering_primitives.py)
- [Runnable examples](examples/)
- [Publishing and citation](docs/publishing.md)

## Limits and engineering posture

- Timoshenko is alpha software and is not a structural safety certification tool.
- Its shear-building model is a small lumped-mass reference model, not a full FEM solver.
- Modal identification is a screening estimate. A single sensor may miss a mode near a modal node.
- Damping is reported only when the averaged spectrum resolves the half-power bandwidth; otherwise it is `None`.
- FDD requires synchronized channels and does not estimate damping.
- The model update applies a single stiffness scale. It cannot locate or size local damage.
- A frequency shift is evidence for human review, not a damage verdict. Temperature, sensor placement, boundary conditions, and other effects can shift measurements.
- A monitoring session consumes data supplied by the caller. It does not implement a broker subscription, reconnect loop, scheduler, hosted dashboard, or alarm policy.
- Closed-form mechanics and section functions rely on their documented ideal assumptions. They are not code-compliance checks.

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest
```

To build the documentation locally, install the optional documentation tools
and run MkDocs:

```bash
python -m pip install -e ".[docs]"
python -m mkdocs serve
```

The test suite checks analytical cases, input validation, adapters, storage,
monitoring sessions, and reports. Package distributions should be built and
installed in a clean environment before a release is uploaded.

## License

Apache License 2.0. See [LICENSE](LICENSE).
