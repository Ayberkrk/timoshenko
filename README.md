# Timoshenko Engine

Timoshenko is a Python library for structural engineering work that project teams often implement repeatedly: representing a simple structure, loading sensor observations, estimating modal frequencies, comparing them with a reference model, and returning evidence in a common format.

Release **0.1.0** is an early, deliberately narrow foundation. It includes a lumped-mass shear-building model, one-channel frequency-domain peak picking, CSV/JSON sensor loading, a uniform stiffness model update, and a modal frequency comparison report. It is not a general FEM solver, damage-localization system, continuous monitoring service, or structural safety certification tool.

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

## Sensor files

CSV input requires a header and a numeric column selected by `column`. JSON input may be a numeric array, an object with a `samples` array, or an array of objects with the selected column. Sampling frequency is required and is never guessed from the filename. A series must contain at least eight finite values. Timestamps/irregularly sampled series are not resampled in 0.1.

## Engineering limits in 0.1

- The structural model is a linear, undamped shear building with one lateral degree of freedom per story.
- Modal identification is a Hann-windowed FFT with local peak picking from one channel. It does not calculate mode shapes and can miss a mode at a sensor node.
- The damping estimate uses a half-power bandwidth approximation when the peak supports it.
- Model updating applies a single scale to all story stiffnesses; it cannot locate or size local damage.
- A frequency change is evidence for review, not a damage verdict. Temperature, sensor placement, boundary conditions, and other effects can also shift measured frequencies.
- `monitor` analyzes the supplied batch once. Continuous subscriptions, persistence, field protocols, dashboards, and alarm policies are planned separately.

## Roadmap

See [yolharitasi.md](yolharitasi.md) for the 0.x release plan, boundaries, and change log.
