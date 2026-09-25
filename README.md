# Timoshenko Engine

Timoshenko is a Python library for structural engineering work that project teams often implement repeatedly: representing a simple structure, loading sensor observations, estimating modal frequencies, comparing them with a reference model, and returning evidence in a common format.

Release **1.9.0** adds geometric area properties for simple polygonal sections with optional holes, including centroid, product of inertia and directional elastic moduli. Release 1.8 adds idealized symmetric I-section and uniform-wall rectangular-tube properties; 1.7 adds a reusable two-mode Rayleigh damping coefficient fit and frequency-curve evaluator; 1.6 adds scalar uncertainty propagation around built-in or user equations. Earlier releases add OGC SensorThings and CSV sources, SQLite session restoration, optional Paho MQTT, versioned source plugins, HTML/SVG reports, idempotent local history, project manifests, and optional Cauren interoperability. Equations remain directly callable as `tm.function_name(...)`; Timoshenko does not provide structural safety certification.

## Install from this checkout

```bash
python -m pip install ./Timoshenko
```

After publication, the intended distribution install name is `timoshenko-engine`; the Python import name is `timoshenko`.

## Python API

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

# Or run the same one-shot sequence as a convenience:
result = tm.monitor(structure, sensors)
print(result.to_dict())
```

The update uses one global multiplier for all story stiffness values. It preserves the original analytical modal frequencies as the reference and records the measured frequencies separately. `health.assess` compares those observed frequencies with that preserved reference; it reports shifts and evidence status without assigning a safety class or failure probability.

## Reusable engineering calculations (0.2)

The modules use SI units and explicit physical inputs. They are small calculation primitives, not design-code checks:

```python
import timoshenko as tm

section = tm.rectangle_section(width_m=0.30, height_m=0.50)
stress = tm.bending_stress(
    moment_nm=12_000.0,
    section_modulus_m3=section.section_modulus_y_m3,
)
tip = tm.beams.cantilever_tip_load(
    load_n=2_000.0,
    span_m=3.0,
    youngs_modulus_pa=30e9,
    second_moment_m4=section.second_moment_y_m4,
    shear_modulus_pa=12.5e9,
    area_m2=section.area_m2,
)
frequency = tm.natural_frequency_hz(mass_kg=1_000.0, stiffness_n_m=2e6)
critical_load = tm.euler_critical_load(
    youngs_modulus_pa=200e9,
    second_moment_m4=section.second_moment_y_m4,
    length_m=3.0,
    effective_length_factor=1.0,
)
shaft = tm.circular_shaft_torsion(
    torque_nm=500.0, length_m=2.0, shear_modulus_pa=80e9, outer_diameter_m=0.04
)
```

`tm.sections` includes rectangles, solid/circular tubes, and in 1.8 idealized symmetric I-sections and uniform-wall rectangular tubes. `tm.polygon_section(outer, holes=...)` calculates geometric properties for user-defined simple polygon boundaries; see [section-properties.md](docs/section-properties.md). `tm.mechanics` includes axial/bending/average shear stress, rectangular peak shear stress, uniaxial elastic strain, free thermal strain, and the isotropic `E`–`G`–Poisson relation. `tm.beams` includes four standard static load cases. Beam functions report Euler–Bernoulli bending deflection; pass both `shear_modulus_pa` and `area_m2` to also calculate a first-order shear term. `tm.vibration` provides undamped SDOF natural frequency, viscous damping ratio, and steady-state harmonic response. Version 0.3 adds `tm.shafts.circular_shaft_torsion`, `tm.stability.euler_critical_load`, `tm.strength.plane_stress`, and `tm.pressure.thin_wall_cylinder_stress`. Common formulas are also re-exported at the top level, so users can call names such as `tm.axial_stress(...)`, `tm.cantilever_tip_load(...)`, `tm.natural_frequency_hz(...)`, `tm.euler_critical_load(...)`, `tm.i_section(...)`, or `tm.thin_wall_cylinder_stress(...)` directly.

These closed-form equations assume the stated idealized geometry, loading, material behavior, and boundary conditions. They do not account for strength limits, buckling, fatigue, load combinations, code factors, nonlinear response, or project-specific acceptance criteria. Validate engineering inputs and applicability independently.

## Multi-channel modal screening (0.4)

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

This first FDD implementation returns candidate frequencies and complex mode shapes for synchronized channels with one common sample rate and unit. It does not estimate damping or issue a damage/safety conclusion. Details and limits are in [numerical-methods.md](docs/numerical-methods.md).

## Cauren integration (0.5)

Cauren can optionally use Timoshenko's generic single-channel modal calculation and shear-building eigenfrequencies. In a shared development environment, install this library with `python -m pip install -e ./Timoshenko`; Cauren's current physics calls will delegate when it can import `timoshenko`. Cauren remains installable without the package and uses its existing pure-Python implementations as a fallback. See [cauren-integration.md](docs/cauren-integration.md).

## Reproducible project workflow (0.6)

```python
project = tm.load_project("project/manifest.json")
result = tm.run_project(project)
print(result.to_dict())
```

The manifest specifies, rather than guesses, the model, CSV path, channels, sample rate, method, and options. The output includes input hashes and the resolved paths for traceability. See [project-manifest.md](docs/project-manifest.md) for the schema and runnable synthetic example.

## Local digital-twin history (0.7)

```python
from timoshenko import Asset, Observation, ObservationBatch, Relation, SQLiteStore

with SQLiteStore("project/history.sqlite") as store:
    store.upsert_asset(Asset("bridge-01", "bridge", "Bridge 01"))
    store.upsert_asset(Asset("accel-01", "sensor", "Deck accelerometer"))
    store.add_relation(Relation("bridge-01", "has_sensor", "accel-01"))
    batch = ObservationBatch(
        [Observation("accel-01", "acceleration", "m/s^2", 0.12, timestamp=1_800_000_000.0, asset_id="bridge-01")],
        batch_id="collector-7:sequence-42",
        source_id="collector-7",
    )
    receipt = store.append_batch(batch)  # repeating the same batch is idempotent
    observations = store.observations(sensor_id="accel-01", order_by="event_time")
```

SQLite is local persistence only. Batch IDs are required; the same ID with changed contents raises an error. The store preserves late/out-of-order observations and lets reads select event-time or arrival ordering. It does not connect to MQTT/OPC UA, resample signals, or execute a live analysis loop. See [storage.md](docs/storage.md).

## Bounded live analysis session (0.8)

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
result = session.ingest(batch)  # timestamped tm.ObservationBatch from your collector
for report in result.reports:
    tm.report.save_html(report, "reports/latest.html")
```

The session aligns samples to the explicit rate, counts rejected records, waits for a fresh contiguous window after gaps, and returns reports after each configured hop. A source/gateway remains responsible for collecting data and reconnecting. See [live-sessions.md](docs/live-sessions.md) and [examples/live_session.py](examples/live_session.py).

When SQLite history is enabled, a new process can refill its bounded sample buffers before starting the source runner:

```python
session = tm.MonitoringSession(structure, ..., store=store)
restore = session.restore()
if not restore.ready_for_analysis:
    print("Waiting for a full fresh window", restore.to_dict())
```

Restoration uses the newest common contiguous timestamped samples with matching units and quality. It does not replay old analysis reports or restore the model object; the application supplies the desired structure definition.

## Readable report output (0.9)

```python
html = tm.report.to_html(result)
report_path = tm.report.save_html(result, "reports/bridge-analysis.html")
```

Reports are standalone HTML with an embedded SVG frequency comparison; no browser framework or plotting dependency is required. They include the method/status, modal table, reference-to-observation differences, evidence summary, and interpretation limitations. Manifest-based runs also include input and manifest SHA-256 values. See [reporting.md](docs/reporting.md).

## Source adapter lifecycle (0.10)

```python
with tm.SessionRunner(source, session, max_batches=1000) as runner:
    for ingest_result in runner:
        for report in ingest_result.reports:
            consume(report)
```

Implement `open()`, `read_batch()`, and `close()` on your gateway. `read_batch()` returns a `tm.ObservationBatch`, or `None` at end-of-stream. The runner does not implement transport reconnects or retries. See [adapters.md](docs/adapters.md).

## Optional source plugins (1.1)

```python
registry = tm.PluginRegistry.load_entry_points()
source = registry.create_source("my-gateway", endpoint="gateway.local")
```

Plugins declare `name`, `api_version`, and `register(registry)`. Discovery is opt-in and installed code runs in-process. See [plugin-contract.md](docs/plugin-contract.md).

## Optional MQTT ingestion (1.2)

```bash
python -m pip install './Timoshenko[mqtt]'
```

After installing the optional Paho client, discover the built-in `mqtt` source plugin and pass it to `SessionRunner`. It validates each JSON publication as a timestamped `ObservationBatch` and acknowledges QoS 1/2 only after successful ingestion. After publishing, install with `python -m pip install 'timoshenko-engine[mqtt]'`. See [mqtt-adapter.md](docs/mqtt-adapter.md).

## Historical CSV replay (1.4)

```python
source = tm.CSVObservationSource(
    "measurements.csv",
    source_id="bridge-01:inspection-2026-09",
    batch_size=128,
)
with tm.SessionRunner(source, session) as runner:
    for result in runner:
        print(result.to_dict())
```

The source reads a long-format CSV incrementally and preserves the declared units and row order. Column names can be mapped explicitly. It does not infer units, interpolate gaps, or tail a changing file. See [csv-source.md](docs/csv-source.md) and [`examples/replay_csv.py`](examples/replay_csv.py).

## OGC SensorThings observation pages (1.5)

```python
source = tm.SensorThingsObservationSource(
    "https://sensors.example.org/v1.1/Datastreams(42)/Observations",
    sensor_id="bridge-01-accel-z",
    unit="m/s^2",
    source_id="bridge-01:datastream-42",
    bearer_token=token,
    quality_parameter="measurement_valid",
)
with tm.SessionRunner(source, session) as runner:
    for result in runner:
        consume(result)
```

The adapter requests the configured collection as JSON and follows each server page link without modifying its query. It accepts scalar numeric results with timezone-aware instant `phenomenonTime`; the caller provides the sensor identity and unit. See [sensorthings-adapter.md](docs/sensorthings-adapter.md).

## Equation uncertainty (1.6)

```python
estimate = tm.uncertainty.propagate(
    tm.natural_frequency_hz,
    {"mass_kg": 120_000.0, "stiffness_n_m": 85_000_000.0},
    standard_uncertainties={"mass_kg": 600.0, "stiffness_n_m": 4_250_000.0},
)
print(estimate.to_dict())
```

Wrap a built-in or user equation to return its estimate, propagated standard uncertainty, coverage interval, and (for first-order propagation) input sensitivities. See [uncertainty.md](docs/uncertainty.md) and [`examples/propagate_uncertainty.py`](examples/propagate_uncertainty.py).

## Rayleigh damping coefficients (1.7)

```python
damping = tm.rayleigh_damping_coefficients(
    frequency_1_hz=0.8,
    damping_ratio_1=0.02,
    frequency_2_hz=4.0,
    damping_ratio_2=0.02,
)
print(damping.to_dict())
print(damping.modal_damping_ratio(2.0))
```

This fits `C = alpha_M M + beta_K K` at two targets; it does not build the damping matrix or select the model for an FEM analysis. See [rayleigh-damping.md](docs/rayleigh-damping.md).

## Common section properties (1.8)

```python
i = tm.i_section(
    overall_width_m=0.20,
    overall_height_m=0.30,
    web_thickness_m=0.01,
    flange_thickness_m=0.015,
)
box = tm.rectangular_tube_section(
    outer_width_m=0.20,
    outer_height_m=0.30,
    wall_thickness_m=0.01,
)
```

These are sharp-corner geometric formulas; they do not replace catalog properties for a named manufactured shape or check its design strength. See [section-properties.md](docs/section-properties.md).

## Sensor files

CSV input requires a header and a numeric column selected by `column`. JSON input may be a numeric array, an object with a `samples` array, or an array of objects with the selected column. Sampling frequency is required and is never guessed from the filename. A series must contain at least eight finite values. Timestamps/irregularly sampled series are not resampled in 0.1.

## Engineering limits

- The structural model is a linear, undamped shear building with one lateral degree of freedom per story.
- Modal identification is a Hann-windowed FFT with local peak picking from one channel. It does not calculate mode shapes and can miss a mode at a sensor node.
- The damping estimate uses a half-power bandwidth approximation when the peak supports it.
- Model updating applies a single scale to all story stiffnesses; it cannot locate or size local damage.
- A frequency change is evidence for review, not a damage verdict. Temperature, sensor placement, boundary conditions, and other effects can also shift measured frequencies.
- `monitor` analyzes the supplied batch once. `MonitoringSession` adds a bounded caller-fed window loop, but no broker subscription, reconnection, background scheduler, dashboard, or alarm policy.
- The 0.2 mechanics and beam functions use idealized linear formulas and SI units; they are not a general-purpose solver or code-compliance engine.
- The 0.3 column, shaft, stress-transformation, and pressure-vessel formulas have narrowly stated ideal assumptions. They do not check slenderness applicability, material yield, local instability, pressure-vessel codes, stress concentrations, or combined loading outside the documented plane-stress calculation.
- `tm.uncertainty.propagate` (1.6) propagates user-provided input uncertainty; it does not infer sensor/model uncertainty, identify distributions, or estimate reliability. First-order propagation can be inaccurate for nonlinear models; Monte Carlo assumes a multivariate Gaussian input distribution and fails explicitly if sampled inputs leave the equation's valid domain. See [uncertainty.md](docs/uncertainty.md).

## Roadmap

See [yolharitasi.md](yolharitasi.md) for the 0.x release plan, boundaries, and change log.
