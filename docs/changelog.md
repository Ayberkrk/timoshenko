# Changelog

Timoshenko follows [semantic versioning](https://semver.org/). While the
package is alpha, minor releases may still refine the API, and any behavior
change is listed here.

## Unreleased

- Multi-channel CSV loading now rejects blank sample lines instead of silently
  dropping them and shifting the time alignment.
- Added a linear elastic planar frame model with supports, nodal loads,
  point and uniform local member loads, end releases, prescribed support
  movements, reactions, member end actions and optional normal stresses.
- Added an iterative P-delta tangent stiffness option for second-order
  screening under axial force.
- Added planar axial bars for truss assembly.
- Added frame natural frequencies, modal participation and effective modal
  masses using explicit lumped and member mass inputs.
- Added MAC comparison for mapped mode shapes and system eigenvalue buckling
  factors for an explicit proportional reference load pattern.
- Modal analysis now statically condenses free degrees of freedom with exactly
  zero mass and recovers their components in the mode shapes.
- Added principal inertias and elastic coupled bending stress for polygon
  sections.
- Added verification examples and documented analysis assumptions and scope.
- Member point forces and point moments on a frame member with a shear area
  use equivalent nodal loads consistent with the shear-flexible stiffness.
  The cubic Euler-Bernoulli equivalents used before gave wrong displacements,
  reactions and end actions for off-centre loads on such members.
- Added JSON-ready `to_dict()` to the static, modal and buckling analysis
  results.
- Added `FrameSection.from_properties` to map principal geometric properties
  and matching section moduli into planar frame bending data.
- Added support for multi-channel FDD input in `tm.monitor`, forwarding
  estimator options to the selected identification method.
- Standardized planar structural validation on the shared finite and positive
  value checks.
- CI now tests and declares support for Python 3.14.

### Changed

- Refined single-channel and FDD peak frequencies with three-point
  interpolation of the log spectrum; `resolution_hz` remains the FFT-bin
  spacing.

## 2.0.3

- The package ships a `py.typed` marker, so type checkers use its annotations.
  `SensorData.samples` is annotated to accept NumPy arrays, which it always did
  at runtime.
- Continuous integration runs `ruff` and `mypy` and publishes a coverage badge.
- Documentation is hosted on Read the Docs, and the package `Documentation`
  link points there.
- Contribution guide, issue and pull request templates, and a README figure of
  the quick start result.

## 2.0.2

- Example and documentation page that verify PyNite shear-deformable members
  against closed-form Timoshenko results (`examples/pynite_shear_beam.py`).
- First release archived on Zenodo, giving the software a citable DOI.

## 2.0.1

- First release published on PyPI as `timoshenko-engine`.
- Package metadata: SPDX license expression, author, keywords, and project URLs.
- Documentation site configuration, citation metadata (`CITATION.cff`), and a
  tested release workflow using PyPI trusted publishing.
- Documentation reorganized by topic with an API reference and this changelog.

## 2.0.0

An audit release. It changes behavior in ways that can affect existing callers.

**Changed**

- Observed modes are paired with reference modes by nearest log-frequency
  (`tm.modal.pair_modes`) instead of by position. A mode missed at a sensor
  node, or a spurious peak, is no longer compared with the wrong mode.
  `ModeChange.mode_number` is now the paired reference mode, and
  `observed_mode_number` gives the position in the modal result.
- `review_recommended` is raised only when `review_threshold_pct` is supplied,
  and never for a change within the spectral resolution (`resolution_limited`).
- Single-channel damping is computed from an averaged Welch spectrum and is
  `None` when the half-power bandwidth is not resolved. It is a screening
  estimate with roughly a factor of two scatter on ambient data.
- `load_sensors` rejects blank samples instead of dropping them.
- `MonitoringSession` validates analysis options when it is created, persists a
  batch only after processing it, and always reports model updates relative to
  the original model.

**Fixed**

- The SensorThings source no longer follows HTTP redirects to another origin,
  which could forward the bearer token.
- Session ingestion cost no longer grows with the window size.

**Added**

- Regression test suite checked against closed-form solutions, and continuous
  integration on Python 3.10 to 3.13.

## Development history before 2.0

These versions were developed before the first public release:

- 1.9: polygon section properties with holes.
- 1.8: ideal I-section and rectangular tube properties.
- 1.7: Rayleigh damping coefficient fit.
- 1.6: first-order and Monte Carlo uncertainty propagation.
- 1.5: OGC SensorThings observation source.
- 1.4: CSV observation replay.
- 1.3: monitoring session restore from SQLite.
- 1.2: optional MQTT observation source.
- 1.1: versioned source plugins.
- 0.1 to 0.10: shear-building model and modal identification, engineering
  primitives, member mechanics, multi-channel FDD, project manifests, SQLite
  history, monitoring sessions, HTML reports, and the observation source
  lifecycle.
