# Cauren integration

[Cauren](https://github.com/Ayberkrk/cauren) is a civil-engineering diagnostics
prototype that uses Timoshenko as an optional engine. It is a worked example of
how a host application can share Timoshenko's calculations while keeping its
own domain decisions.

## Boundary

Timoshenko owns reusable, domain-independent calculations. Cauren owns its civil
and bridge schemas, sensor-name and unit interpretation, calibrated risk
thresholds, model routing, and engineering review language. A modal frequency
or FDD result is evidence, not a Cauren risk decision.

## How Cauren uses the engine

Cauren's `cauren_physics/timoshenko_adapter.py` loads Timoshenko 2.0 or newer
when it is installed and delegates:

- single-channel modal identification (`tm.modal.identify`),
- mode pairing against baseline frequencies (`tm.modal.pair_modes`),
- multi-channel FDD with mode shapes (`tm.identify_fdd`),
- shear-building natural frequencies (`tm.Structure`),
- the global stiffness update used in its FE model consistency check (`tm.update`).

When Timoshenko is not installed, Cauren runs its own pure-Python
implementations of the same methods, so it keeps no required third-party
dependency. Cauren's test suite runs in both configurations and checks that the
two paths agree. Multi-channel FDD is available only with Timoshenko.

## Enable it

Install Timoshenko into the same environment as Cauren:

```bash
python -m pip install timoshenko-engine
```

Existing Cauren calls then use the engine without code changes:

```python
from cauren_physics.fe_reference_model import ShearBuildingModel, natural_frequencies_hz
from cauren_physics.oma import compare_to_baseline, identify_modal_parameters

building = ShearBuildingModel((50_000.0,), (8_000_000.0,))
theoretical_hz = natural_frequencies_hz(building)
observed = identify_modal_parameters(acceleration_samples, sampling_hz=100.0)
drift = compare_to_baseline(observed, [2.0])
```
