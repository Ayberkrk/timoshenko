# Timoshenko Engine

Timoshenko is an embeddable Python library of reusable structural engineering
building blocks: closed-form calculations, modal analysis, sensor data
workflows, and monitoring components. Applications use it instead of
rebuilding the same foundations, while keeping their own data collection,
interface, and decision rules.

The library is alpha software. Its outputs support engineering review; they
are not a safety certification, a damage diagnosis, or a general finite element
solution.

## Install

```bash
python -m pip install timoshenko-engine
```

```python
import timoshenko as tm

print(tm.cantilever_tip_load(5_000.0, 3.0, 200e9, 8.0e-6).bending_m)
```

## Documentation map

**Start here**

- [Architecture](architecture.md): what the engine owns and what the host application keeps.
- [API reference](api.md): every public function and class with a one-line summary.
- [Numerical methods](numerical-methods.md): equations, algorithms, assumptions, and limits.

**Modal analysis and monitoring**

- [Data contract](data-contract.md): validated sensor data and observation records.
- [Live sessions](live-sessions.md): bounded rolling-window analysis and restart.
- [Project manifests](project-manifest.md): repeatable one-shot runs with provenance.
- [Reports](reporting.md): standalone HTML evidence reports.

**Data sources and storage**

- [Source adapters](adapters.md) and the [plugin contract](plugin-contract.md).
- [CSV replay](csv-source.md), [MQTT](mqtt-adapter.md), and [OGC SensorThings](sensorthings-adapter.md).
- [Local SQLite history](storage.md).

**Engineering calculations**

- [Section properties](section-properties.md) and [polygon sections](polygon-sections.md).
- [Rayleigh damping](rayleigh-damping.md).
- [Uncertainty propagation](uncertainty.md).

**Project**

- [Changelog](changelog.md).
- [Literature review](literature-review.md): sources behind the methods and their limits.
- [Cauren integration](cauren-integration.md): an example of a host application.
- [Publishing and citation](publishing.md).
