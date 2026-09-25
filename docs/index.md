# Timoshenko Engine

Timoshenko is an embeddable Python library for reusable structural engineering
calculations, modal analysis, sensor data workflows, and monitoring components.
It is designed to provide common engineering building blocks to applications
such as Cauren without taking over their data collection, interface, or
project-specific decision rules.

The library is alpha software. Its outputs support engineering review and are
not a safety certification, damage diagnosis, or general finite element
solution.

## Install

The `timoshenko-engine` distribution exposes the `timoshenko` Python package.
Until a package release is available from PyPI, install from the repository
root:

```bash
python -m pip install .
```

```python
import timoshenko as tm

structure = tm.Structure(
    structure_id="building-01",
    story_masses_kg=[120_000.0, 110_000.0],
    story_stiffness_n_m=[85_000_000.0, 70_000_000.0],
)
```

## Documentation map

- [Architecture](architecture.md) describes the engine boundary and how host
  applications compose its modules.
- [Data contract](data-contract.md) and [project manifest](project-manifest.md)
  describe validated inputs and repeatable local runs.
- [Numerical methods](numerical-methods.md) documents algorithms, assumptions,
  and analysis limits.
- [Live sessions](live-sessions.md), [source adapters](adapters.md), and
  [local storage](storage.md) cover monitoring workflows and data handling.
- [Engineering calculations](section-properties.md) cover section properties,
  mechanics, damping, and uncertainty.
- [Release and citation setup](publishing.md) records the package publication,
  versioned docs, and Zenodo integration steps.

Read the Docs and Zenodo repository integrations are configured in this source
tree but are not active until the GitHub repository is connected to those
services. Read the Docs will build the active Git tags as documentation
versions after its project is configured.
