<p align="center">
  <img src="https://raw.githubusercontent.com/Ayberkrk/timoshenko/main/assets/timoshenko-logo.png" alt="Timoshenko Engine logo" width="920">
</p>

<h1 align="center">Timoshenko Engine</h1>

<p align="center">
  Reusable structural engineering building blocks for Python applications.
</p>

<p align="center">
  <a href="https://pypi.org/project/timoshenko-engine/"><img alt="PyPI" src="https://img.shields.io/pypi/v/timoshenko-engine?style=for-the-badge"></a>
  <img alt="Python versions" src="https://img.shields.io/pypi/pyversions/timoshenko-engine?style=for-the-badge">
  <img alt="Alpha" src="https://img.shields.io/badge/stage-alpha-orange?style=for-the-badge">
  <img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache--2.0-green?style=for-the-badge">
  <a href="https://doi.org/10.5281/zenodo.22968739"><img alt="DOI" src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.22968739-blue?style=for-the-badge"></a>
  <a href="https://github.com/Ayberkrk/timoshenko/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/Ayberkrk/timoshenko/actions/workflows/tests.yml/badge.svg"></a>
</p>

Timoshenko packages common structural calculations, modal analysis, sensor
workflows, and monitoring components so applications can reuse them instead
of rebuilding the same foundations for every project. It is an embeddable
Python library, not a hosted monitoring service or a general finite-element
solver.

> **Alpha:** the API may still change between releases. Every behavior change
> is listed in the [changelog](https://github.com/Ayberkrk/timoshenko/blob/main/docs/changelog.md).

## Install

```bash
python -m pip install timoshenko-engine
```

The distribution is named `timoshenko-engine`; the import package is
`timoshenko`. Optional MQTT support is an extra:

```bash
python -m pip install "timoshenko-engine[mqtt]"
```

## Quick start

Compare measured vibration with a reference model. This example simulates a
record in which both modes are 5% below the model:

```python
import numpy as np
import timoshenko as tm

structure = tm.Structure(
    structure_id="building-01",
    story_masses_kg=[120_000.0, 110_000.0],
    story_stiffness_n_m=[85_000_000.0, 70_000_000.0],
)
print(structure.natural_frequencies_hz)          # (2.626, 6.476)

fs = 100.0
t = np.arange(60_000) / fs
f1, f2 = (0.95 * f for f in structure.natural_frequencies_hz)
signal = np.sin(2 * np.pi * f1 * t) + 0.4 * np.sin(2 * np.pi * f2 * t)
sensors = tm.SensorData(signal, sampling_hz=fs, unit="m/s^2")

result = tm.monitor(structure, sensors, review_threshold_pct=3.0)
print(result.structure.update_scale_factor)      # 0.903, since stiffness scales with frequency squared
for change in result.health.mode_changes:
    print(change.mode_number, change.change_pct)  # 1 -5.0, then 2 -5.0
print(result.health.review_recommended)          # True
```

Real records load from CSV or JSON with
`tm.load_sensors("acceleration.csv", sampling_hz=100.0, column="acc")`. The
steps inside `tm.monitor` are also available separately as `tm.modal.identify`,
`tm.update`, and `tm.health.assess`. The review flag is raised only when you
pass a threshold: a meaningful value depends on the structure and its
environmental variability, so the engine does not choose one.

## Engineering calculations

Closed-form functions take and return SI units and validate their inputs:

```python
import timoshenko as tm

section = tm.rectangle_section(width_m=0.3, height_m=0.6)
beam = tm.simply_supported_uniform_load(
    20_000.0, 6.0, 30e9, section.second_moment_y_m4,
    shear_modulus_pa=12.5e9, area_m2=section.area_m2,
)
print(beam.bending_m, beam.shear_m)  # 2.083 mm bending, 0.048 mm shear

frequency = tm.propagate_uncertainty(
    tm.natural_frequency_hz,
    {"mass_kg": 250.0, "stiffness_n_m": 4e5},
    standard_uncertainties={"mass_kg": 5.0, "stiffness_n_m": 8e3},
)
print(frequency.estimate, frequency.standard_uncertainty)  # 6.366 Hz ± 0.090 Hz
```

## What it provides

| Area | Components |
|---|---|
| Engineering calculations | Section properties (including polygons with holes), beam deflection with shear, torsion, Euler buckling, plane stress, thin-wall pressure, SDOF vibration, Rayleigh damping, and GUM / Monte Carlo uncertainty |
| Structural models | Lumped-mass shear-building models and their natural frequencies |
| Modal analysis | Single-channel peak picking with resolution-checked damping, and multi-channel FDD with complex mode shapes |
| Model comparison | Nearest-frequency mode pairing, global stiffness updating, and evidence-oriented health assessment |
| Monitoring | Bounded rolling-window sessions, restart from local history, and source adapters for CSV, MQTT, and OGC SensorThings |
| Data and reporting | Project manifests with SHA-256 provenance, local SQLite history, and standalone HTML reports |

Sensor collection, alarm policy, and engineering interpretation remain with the
application that embeds Timoshenko.

## Multi-channel modal analysis

Frequency domain decomposition needs synchronized channels with a common
sample rate and unit:

```python
signals = tm.load_multichannel_csv(
    "aligned_accelerometers.csv",
    columns=["deck_left", "deck_center", "deck_right"],
    sampling_hz=100.0,
    units=["m/s^2"] * 3,
)
fdd = tm.identify_fdd(signals, nperseg=1024, max_modes=5)
for mode in fdd.modes:
    print(mode.frequency_hz, mode.shape_real)
```

## Monitoring sessions

A host application feeds timestamped observation batches. The session aligns
samples to the sample grid, waits for a fresh contiguous window after gaps, and
analyzes every configured hop:

```python
session = tm.MonitoringSession(
    structure,
    sensor_ids=["deck-left", "deck-right"],
    units=["m/s^2", "m/s^2"],
    sampling_hz=100.0,
    window_samples=2048,
    hop_samples=512,
    analysis_options={"nperseg": 512, "max_modes": 4},
    review_threshold_pct=5.0,
)
result = session.ingest(batch)  # batch: tm.ObservationBatch from your gateway or a source adapter
for report in result.reports:
    tm.report.save_html(report, "reports/latest.html")
```

The session does not open network connections or run in the background. Use
`tm.SessionRunner` with a source such as `tm.CSVObservationSource` or
`tm.MqttObservationSource` to drive it.

## Documentation

- [Documentation home](https://github.com/Ayberkrk/timoshenko/blob/main/docs/index.md)
- [API reference](https://github.com/Ayberkrk/timoshenko/blob/main/docs/api.md)
- [Numerical methods and limits](https://github.com/Ayberkrk/timoshenko/blob/main/docs/numerical-methods.md)
- [Architecture](https://github.com/Ayberkrk/timoshenko/blob/main/docs/architecture.md)
- [Monitoring sessions](https://github.com/Ayberkrk/timoshenko/blob/main/docs/live-sessions.md) and [source adapters](https://github.com/Ayberkrk/timoshenko/blob/main/docs/adapters.md)
- [Runnable examples](https://github.com/Ayberkrk/timoshenko/tree/main/examples), including a [cross-check of PyNite shear-deformable beams](https://github.com/Ayberkrk/timoshenko/blob/main/docs/pynite-verification.md)
- [Changelog](https://github.com/Ayberkrk/timoshenko/blob/main/docs/changelog.md)

## Limits and engineering posture

- Timoshenko is alpha software and is not a structural safety certification tool.
- The shear-building model is a small lumped-mass reference model, not a full FEM solver.
- Modal identification is a screening estimate. A single sensor may miss a mode near a modal node; unpaired peaks are reported rather than compared with the wrong mode.
- Damping is a coarse screening estimate, reported only when the averaged spectrum resolves the half-power bandwidth. FDD does not estimate damping.
- The model update applies a single stiffness scale. It cannot locate or size local damage.
- A frequency shift is evidence for human review, not a damage verdict. Temperature, sensor placement, boundary conditions, and other effects also shift measured frequencies.
- Closed-form mechanics and section functions rely on their documented ideal assumptions. They are not code-compliance checks.

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest
```

To preview the documentation site:

```bash
python -m pip install -e ".[docs]"
python -m mkdocs serve
```

Bug reports and pull requests are welcome in the
[issue tracker](https://github.com/Ayberkrk/timoshenko/issues).

## Citation

If you use Timoshenko in research, please cite it with its DOI,
[10.5281/zenodo.22968739](https://doi.org/10.5281/zenodo.22968739), which
always resolves to the latest release; each release also has its own DOI on
[Zenodo](https://zenodo.org/records/22968740). The metadata is in
[`CITATION.cff`](https://github.com/Ayberkrk/timoshenko/blob/main/CITATION.cff),
which GitHub's "Cite this repository" button reads.

## License

Apache License 2.0. See [LICENSE](https://github.com/Ayberkrk/timoshenko/blob/main/LICENSE).
