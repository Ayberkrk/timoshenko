# Timoshenko Engine

Timoshenko is a Python library for structural engineering work that project teams often implement repeatedly: representing a simple structure, loading sensor observations, estimating modal frequencies, comparing them with a reference model, and returning evidence in a common format.

Release **0.3.0** builds on the 0.1 monitoring and 0.2 calculation foundations. It adds common circular-shaft torsion, ideal elastic Euler column stability, plane-stress transformations, and thin-wall cylinder estimates, with selected functions available both as `tm.function_name(...)` and under focused modules. It is still not a general FEM solver, damage-localization system, continuous monitoring service, or structural safety certification tool.

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

`tm.sections` includes rectangular, solid circular, and concentric circular-tube properties. `tm.mechanics` includes axial/bending/average shear stress, rectangular peak shear stress, uniaxial elastic strain, free thermal strain, and the isotropic `E`–`G`–Poisson relation. `tm.beams` includes four standard static load cases. Beam functions report Euler–Bernoulli bending deflection; pass both `shear_modulus_pa` and `area_m2` to also calculate a first-order shear term. `tm.vibration` provides undamped SDOF natural frequency, viscous damping ratio, and steady-state harmonic response. Version 0.3 adds `tm.shafts.circular_shaft_torsion`, `tm.stability.euler_critical_load`, `tm.strength.plane_stress`, and `tm.pressure.thin_wall_cylinder_stress`. Common formulas are also re-exported at the top level, so users can call names such as `tm.axial_stress(...)`, `tm.cantilever_tip_load(...)`, `tm.natural_frequency_hz(...)`, `tm.euler_critical_load(...)`, or `tm.thin_wall_cylinder_stress(...)` directly.

These closed-form equations assume the stated idealized geometry, loading, material behavior, and boundary conditions. They do not account for strength limits, buckling, fatigue, load combinations, code factors, nonlinear response, or project-specific acceptance criteria. Validate engineering inputs and applicability independently.

## Sensor files

CSV input requires a header and a numeric column selected by `column`. JSON input may be a numeric array, an object with a `samples` array, or an array of objects with the selected column. Sampling frequency is required and is never guessed from the filename. A series must contain at least eight finite values. Timestamps/irregularly sampled series are not resampled in 0.1.

## Engineering limits

- The structural model is a linear, undamped shear building with one lateral degree of freedom per story.
- Modal identification is a Hann-windowed FFT with local peak picking from one channel. It does not calculate mode shapes and can miss a mode at a sensor node.
- The damping estimate uses a half-power bandwidth approximation when the peak supports it.
- Model updating applies a single scale to all story stiffnesses; it cannot locate or size local damage.
- A frequency change is evidence for review, not a damage verdict. Temperature, sensor placement, boundary conditions, and other effects can also shift measured frequencies.
- `monitor` analyzes the supplied batch once. Continuous subscriptions, persistence, field protocols, dashboards, and alarm policies are planned separately.
- The 0.2 mechanics and beam functions use idealized linear formulas and SI units; they are not a general-purpose solver or code-compliance engine.
- The 0.3 column, shaft, stress-transformation, and pressure-vessel formulas have narrowly stated ideal assumptions. They do not check slenderness applicability, material yield, local instability, pressure-vessel codes, stress concentrations, or combined loading outside the documented plane-stress calculation.

## Roadmap

See [yolharitasi.md](yolharitasi.md) for the 0.x release plan, boundaries, and change log.
