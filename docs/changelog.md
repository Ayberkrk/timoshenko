# Changelog

Timoshenko follows [semantic versioning](https://semver.org/). While the
package is alpha, minor releases may still refine the API, and any behavior
change is listed here.

## Unreleased

- `tm.HarmonicResponse`, the result type of `tm.harmonic_response`, is
  exported from the top-level package.

## 2.1.0

Adds planar structural analysis: frames and trusses with static, P-delta,
modal and buckling analysis. Two changes affect results from existing code;
they are listed under "Changed".

**Added**

- A linear elastic planar model, `tm.StructuralModel`, built from nodes, frame
  members and axial bars, with ideal supports, prescribed support movements,
  nodal loads, member point forces and moments, full-span uniform loads,
  partial-span uniform loads (`tm.FramePartialUniformLoad`) and rotational
  end releases.
- `tm.analyze_linear_static` returns displacements, reactions, member end
  actions, optional end normal stresses, strain energy and equilibrium
  residuals.
- Frame members use Timoshenko shear-flexible stiffness when an effective
  shear area is supplied, and Euler-Bernoulli stiffness otherwise. Member
  load equivalents use the shape functions of the same stiffness, so a
  loaded member gives the same nodal response as the member split at the
  load.
- `tm.recover_member_response` recovers axial force, shear, bending moment
  and transverse deflection along a frame member from a first-order static
  result, with the moment extrema and their locations.
- `tm.analyze_p_delta` iterates a tangent stiffness for second-order
  screening under axial force.
- `tm.analyze_modes` returns natural frequencies, mode shapes, participation
  factors and effective modal masses from explicit lumped and member mass
  inputs. Free degrees of freedom with exactly zero mass are statically
  condensed, so frames that carry only joint masses can be analyzed, and
  rigid-body modes are reported as exactly 0 Hz.
- `tm.analyze_linear_buckling` returns elastic system buckling load factors
  for one proportional reference load pattern.
- Rotational end releases are supported in static, P-delta, modal and
  buckling analysis.
- `tm.modal_assurance_criterion` compares mapped real or complex mode shapes.
- `tm.FrameSection.from_properties` builds a frame section from
  `SectionProperties` or a polygon section whose axes are principal. The
  bending axis must be named and the effective shear area stays explicit.
- JSON-ready `to_dict()` on the static, member response, modal and buckling
  results.
- Principal inertias and elastic coupled bending stress for polygon sections.
- `tm.monitor` accepts multi-channel data, runs FDD for it, and forwards
  estimator options to the selected identification method.
- Python 3.14 is tested in continuous integration and declared in the package
  metadata.
- Verification examples and a documentation page that states the analysis
  assumptions, sign conventions and scope.

**Changed**

- `tm.modal.identify` and `tm.identify_fdd` refine each peak frequency
  between FFT bins with a three-point interpolation of the log spectrum.
  Identified frequencies are no longer quantized to bin centres, so they can
  differ from 2.0.3 by up to half a bin. `resolution_hz` remains the FFT-bin
  spacing.
- `tm.load_multichannel_csv` rejects blank sample lines instead of silently
  dropping them, which shortened the record and shifted every later sample
  in time. `tm.load_sensors` already behaved this way.
- HTML reports and the `sensor_ids` error message use ASCII hyphens. The
  placeholder for a missing number in a report is now `-`.

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
