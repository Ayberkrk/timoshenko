# API reference

Every name below is available from `import timoshenko as tm`. Names written
with a module prefix, such as `tm.modal.identify`, are reached through that
module. SI units are used throughout; see [numerical methods](numerical-methods.md)
for equations, assumptions and limits.

## Structural model and analysis

Build a lumped-mass shear-building reference model, or analyze a prismatic 2D frame with nodal supports and loads. The frame routines are linear elastic and small displacement.

| Name | Description |
|---|---|
| `tm.Structure` | A shear-building model with one lateral degree of freedom per floor. |
| `tm.StructuralModel` | A planar truss/frame with nodes, prismatic members, restraints, prescribed support displacements, nodal loads and optional lumped masses. |
| `tm.StructuralModel3D` | Separate small, linear 3D truss/frame model with six degrees of freedom per node. |
| `tm.FrameNode3D` | A 3D node with x, y and z coordinates. |
| `tm.FrameMaterial3D` / `tm.FrameSection3D` | Isotropic elastic moduli and prismatic 3D section properties. |
| `tm.FrameMember3D` / `tm.TrussMember3D` | 3D frame and axial truss inputs, including explicit member local-axis orientation. |
| `tm.analyze_linear_static_3d` / `tm.analyze_modes_3d` / `tm.analyze_linear_buckling_3d` | Dense-matrix 3D static, modal and ideal linear buckling analyses. |
| `tm.StaticAnalysis3DResult` / `tm.ModalAnalysis3DResult` | 3D nodal static response or undamped modal frequencies, shapes and participation data. |
| `tm.BucklingAnalysis3DResult` | 3D ideal buckling factors, mode shapes and reference member axial forces. |
| `tm.assemble_matrices_3d` | Assemble global 3D stiffness and mass matrices for advanced caller workflows. |
| `tm.AxialMember` | A two-node axial bar for planar truss assembly. |
| `tm.FrameNode` | A frame node with global x and y coordinates in metres. |
| `tm.FrameMaterial` | Elastic Young's and shear moduli, with an optional isotropic Poisson-ratio consistency check. |
| `tm.FrameSection` | Area, in-plane bending inertia, optional effective shear area and local-y section moduli; `from_properties` maps principal section properties to frame axes. |
| `tm.FrameMember` | A two-node prismatic frame member with optional local point, full-span and partial-span uniform loads, rotational end releases and mass per length. |
| `tm.FramePointLoad` | A local point force and/or moment at a specified distance along a member. |
| `tm.analyze_linear_static` | Assemble and solve one linear static planar load case; return displacements, reactions, member end actions and selected end stresses. |
| `tm.analyze_p_delta` | Iterate an approximate axial-force geometric stiffness for small-displacement 2D frame response. |
| `tm.FrameAnalysisResult` | Frame displacements, reactions, member end actions, selected normal stresses, strain energy and local and global equilibrium residuals. |
| `tm.recover_member_response` | Recover section forces, transverse deflection and moment extrema along one frame member from a first-order static result. |
| `tm.FrameMemberResponse` | Stations, axial/shear forces, bending moments, transverse deflections and signed/absolute moment extrema for one frame member. |
| `tm.FramePartialUniformLoad` | A local x/y uniform load over a start-to-end interval of one frame member. |
| `tm.analyze_modes` | Solve an undamped generalized eigenproblem for a planar model using supplied member and nodal mass. |
| `tm.ModalAnalysisResult` | Natural frequencies, peak-normalized mode shapes, generalized and effective modal masses, and directional participation ratios. |
| `tm.modal_assurance_criterion` | Compare two real or complex mode-shape vectors after the caller maps them to a common degree-of-freedom order. |
| `tm.analyze_linear_buckling` | Estimate ideal elastic system load factors for one explicit proportional reference load pattern. |
| `tm.analyze_time_history` | Integrate a 2D or 3D linear model with Newmark average acceleration and optional Rayleigh damping/base acceleration. |
| `tm.TimeHistoryResult` | Nodal displacement, velocity, acceleration and reaction histories. |
| `tm.BucklingAnalysisResult` | Linear buckling load factors, mode shapes and reference member axial forces. |
| `tm.modal.identify` | Estimate modal peaks with a Hann-windowed single-sided FFT and sub-bin peak interpolation. |
| `tm.modal.pair_modes` | Pair observed with reference frequencies by nearest log-frequency. |
| `tm.ModalResult` | Single-channel identification result: modes sorted by frequency, resolution, status and method notes. |
| `tm.Mode` | One identified peak: frequency, spectral amplitude and damping ratio (`None` when not resolvable). |
| `tm.update` | Scale all story stiffnesses uniformly to fit identified frequencies. |
| `tm.update_story_stiffness` | Estimate individual shear-building story stiffness scales from a complete set of observed modal frequencies. |
| `tm.StoryUpdateResult` | Local story update, fitted frequencies, residual and convergence status. |
| `tm.health.assess` | Compare observed frequencies with the structure's preserved baseline. |
| `tm.HealthAssessment` | Paired mode changes against the baseline, evidence status, optional review flag and interpretation limits. |
| `tm.monitor` | Run single-channel FFT or multi-channel FDD identification, uniform model update, then health comparison; forward estimator options as keyword arguments. |
| `tm.MonitoringResult` | Output of `tm.monitor`: updated structure, single-channel or FDD modal result, and health assessment. |

## Multi-channel modal analysis

Frequency domain decomposition for synchronized channels.

| Name | Description |
|---|---|
| `tm.MultiChannelData` | Aligned array shaped ``(sample, channel)`` with explicit metadata. |
| `tm.load_multichannel_csv` | Read aligned numeric channels from a headered CSV file. |
| `tm.identify_fdd` | Estimate modal frequencies with sub-bin peak interpolation and complex mode shapes with Welch FDD. |
| `tm.identify_ssi` | Estimate stable modal frequencies, damping and mode shapes with covariance-driven SSI. |
| `tm.SSIMode` / `tm.SSIResult` | SSI modal estimates with stability counts/scores and input metadata. |
| `tm.TimedChannel` / `tm.align_multichannel` | Apply explicit clock offsets and calibration, then resample asynchronous channels onto contiguous shared grids. |
| `tm.AlignmentResult` / `tm.AlignedSegment` | Aligned multi-channel segments with timestamps and dropped-grid-point diagnostics. |
| `tm.identify_fdd(..., estimate_damping=True)` | Optionally estimate FDD damping with EFDD; unresolved damping is returned as `None`. |
| `tm.FDDResult` | Multi-channel FDD result: modes, resolution, segment settings, channels and notes. |
| `tm.FDDMode` | One FDD mode: frequency, singular value, and complex mode shape normalized to unit peak magnitude. |

Environmental normalization fits repeated modal-frequency records against explicit environmental covariates:

| Name | Description |
|---|---|
| `tm.fit_environmental_baseline` | Fit per-mode linear frequency trends against named environmental features. |
| `tm.EnvironmentalFrequencyBaseline` | Fitted baseline, reference environment, frequency scatter and normalization method. |

## Sensor data

Single-channel loading and point observations shared by sessions and adapters.

| Name | Description |
|---|---|
| `tm.SensorData` | A single regularly sampled sensor channel. |
| `tm.load_sensors` | Load one numeric channel from CSV, JSON, an array, or SensorData. |
| `tm.Observation` | One sensor value with event time, unit, quality, and provenance metadata. |
| `tm.ObservationBatch` | A batch in arrival order; consumers choose event-time sorting policy. |

## Monitoring sessions

Bounded rolling-window analysis of caller-supplied observation batches.

| Name | Description |
|---|---|
| `tm.MonitoringSession` | Analyze regularly sampled point observations in bounded rolling windows. |
| `tm.SessionIngestResult` | Counts of accepted and rejected observations for one batch, plus any analysis reports produced. |
| `tm.SessionReport` | One analysis of a completed window: event time, method, updated structure, modal result and health. |
| `tm.SessionRestoreResult` | Samples restored from a `SQLiteStore` and whether a full analysis window is ready. |
| `tm.SessionRunner` | Drive one monitoring session from a source with explicit cleanup. |

## Source adapters and plugins

Pull-source contracts, built-in sources and entry-point plugin discovery.

| Name | Description |
|---|---|
| `tm.ObservationSource` | Synchronous pull-source contract for gateways and replay adapters. |
| `tm.AcknowledgingObservationSource` | Optional extension for sources that acknowledge only after ingestion. |
| `tm.CSVObservationSource` | Read long-format sensor CSV incrementally as :class:`ObservationBatch` objects. |
| `tm.CSVSourceError` | Raised when a CSV file cannot be read as the configured observation schema. |
| `tm.MqttObservationSource` | Subscribe to a topic carrying version-1 Timoshenko JSON batch payloads. |
| `tm.MQTTSourceError` | Raised for connection, payload, or bounded-queue failures. |
| `tm.SensorThingsObservationSource` | Read one configured SensorThings Datastream Observations collection. |
| `tm.SensorThingsSourceError` | Raised for SensorThings transport, pagination, or mapping failures. |
| `tm.SensorThingsPlugin` | Built-in source plugin for ``PluginRegistry``. |
| `tm.PluginRegistry` | Registry for optional adapter/source factories supplied by plugins. |
| `tm.EnginePlugin` | Base class for protocol classes. |
| `tm.PluginContributions` | A staging area; contributions become visible only after registration succeeds. |
| `tm.PluginError` | Base exception for invalid or incompatible engine plugins. |
| `tm.PluginCompatibilityError` | Raised when a plugin targets a different plugin API version. |
| `tm.PluginLoadError` | Raised when installed plugin code cannot be loaded or registered. |
| `tm.PLUGIN_API_VERSION` | Plugin API version this engine accepts (`'1'`). |
| `tm.ENTRY_POINT_GROUP` | Entry-point group scanned for plugins (`'timoshenko.plugins'`). |

## Projects, storage and reports

Manifest-driven runs, local SQLite history and HTML reports.

| Name | Description |
|---|---|
| `tm.read_manifest` | Read and validate a version-1 JSON manifest; relative files resolve beside it. |
| `tm.load_project` | Validate a manifest, load its CSV channels, and capture input provenance. |
| `tm.run_project` | Execute one deterministic one-shot analysis described by a manifest. |
| `tm.ProjectManifest` | Validated manifest fields with file paths resolved from its directory. |
| `tm.LoadedProject` | A validated manifest with its loaded observations and SHA-256 hashes of manifest and data. |
| `tm.ProjectRunResult` | Serializable result of `tm.run_project`, including provenance hashes. |
| `tm.SQLiteStore` | A one-process local history store backed by Python's SQLite module. |
| `tm.BatchAppendResult` | Receipt from `SQLiteStore.append_batch`: inserted rows and whether the batch was a duplicate. |
| `tm.Asset` | A monitored asset record with type, name and metadata. |
| `tm.Relation` | A typed, directed relation between two assets. |
| `tm.report.to_html` | Render a self-contained accessible HTML report with a small SVG chart. |
| `tm.report.save_html` | Write a UTF-8 self-contained HTML report and return its resolved path. |

## Section properties

Ideal geometric properties in SI units.

| Name | Description |
|---|---|
| `tm.rectangle_section` | Return centroidal properties; y is the width axis, z the height axis. |
| `tm.solid_circle_section` | Return centroidal properties for a solid circular section. |
| `tm.circular_tube_section` | Return centroidal properties for a concentric circular hollow section. |
| `tm.i_section` | Return centroidal properties of an ideal symmetric sharp-corner I-section. |
| `tm.rectangular_tube_section` | Return centroidal properties of an ideal uniform-wall rectangular tube. |
| `tm.SectionProperties` | Area, second moments, elastic section moduli and principal inertias for standard shape axes; `to_dict()` returns JSON-ready field values. |
| `tm.polygon_section` | Calculate area, centroid, second moments, product moment and moduli. |
| `tm.PolygonSectionProperties` | Geometric properties, principal second moments and principal-axis orientation of a uniform polygonal section (SI units); `to_dict()` returns JSON-ready field values. |
| `tm.polygon_bending_stress_pa` | Calculate elastic axial and coupled biaxial bending stress at caller-supplied polygon coordinates. |

For frame bending in the global x-y plane, pass the section's second moment
about the local z axis as ``FrameSection.second_moment_local_z_m4``. Effective
shear area, section moduli and member mass are explicit inputs; the engine
does not infer them from an arbitrary outline or density. Modal analysis does
not yet support frame-member end releases.

## Mechanics, beams and members

Closed-form linear elastic relations.

| Name | Description |
|---|---|
| `tm.axial_stress` | Average normal stress ``N/A`` in pascals; tension is positive. |
| `tm.bending_stress` | Extreme-fiber elastic bending stress ``M/S`` in pascals. |
| `tm.average_shear_stress` | Average shear stress ``V/A`` in pascals (not a peak-stress estimate). |
| `tm.rectangular_max_shear_stress` | Maximum elastic shear stress ``1.5 V/A`` for a solid rectangle. |
| `tm.axial_strain` | Uniaxial elastic strain ``sigma/E`` (dimensionless). |
| `tm.thermal_strain` | Free isotropic thermal strain ``alpha * delta_T`` (dimensionless). |
| `tm.youngs_modulus_from_shear` | Return ``E = 2 G (1 + nu)`` for an isotropic linear elastic material. |
| `tm.cantilever_tip_load` | Tip deflection of a cantilever with a point load at its free end. |
| `tm.cantilever_uniform_load` | Free-end deflection of a cantilever under a full-span uniform load. |
| `tm.simply_supported_midpoint_load` | Midspan deflection of a simply supported beam with a center point load. |
| `tm.simply_supported_uniform_load` | Midspan deflection of a simply supported beam under full-span UDL. |
| `tm.BeamDeflection` | Bending and shear deflection terms, with their sum as `total_m`; `to_dict()` returns JSON-ready field values. |
| `tm.circular_shaft_torsion` | Return elastic outer-fiber shear stress and twist for a round shaft. |
| `tm.CircularTorsionResult` | Polar moment, outer-fiber shear stress and twist angle of a circular shaft; `to_dict()` returns JSON-ready field values. |
| `tm.euler_critical_load` | Euler elastic critical load ``pi^2 E I / (K L)^2`` in newtons. |
| `tm.slenderness_ratio` | Geometric slenderness ``K L / r_g`` for one selected buckling axis. |
| `tm.plane_stress` | Return principal stresses, in-plane max shear, and plane-stress von Mises. |
| `tm.PlaneStressResult` | Principal stresses, maximum in-plane shear and von Mises equivalent stress; `to_dict()` returns JSON-ready field values. |
| `tm.thin_wall_cylinder_stress` | Estimate membrane stresses in a closed-end thin cylindrical vessel. |
| `tm.ThinWallCylinderResult` | Hoop and longitudinal membrane stresses and the thickness to radius ratio; `to_dict()` returns JSON-ready field values. |

## Vibration and damping

Single-degree-of-freedom relations and proportional damping.

| Name | Description |
|---|---|
| `tm.natural_frequency_hz` | Undamped natural frequency ``sqrt(k/m)/(2*pi)`` for an SDOF system. |
| `tm.damping_ratio` | Viscous damping ratio ``c/(2*sqrt(k*m))``. |
| `tm.harmonic_response` | Steady-state displacement amplitude and phase for a harmonically forced SDOF. |
| `tm.HarmonicResponse` | Result of `tm.harmonic_response`: displacement amplitude, phase lag and frequency ratio; `to_dict()` returns JSON-ready field values. |
| `tm.rayleigh_damping_coefficients` | Fit passive Rayleigh coefficients to two modal damping targets. |
| `tm.RayleighDampingResult` | Two-frequency fit for mass- and stiffness-proportional viscous damping. |

## Uncertainty

First-order (GUM) and Monte Carlo propagation through scalar equations.

| Name | Description |
|---|---|
| `tm.propagate_uncertainty` | Propagate input standard uncertainties through a scalar callable. |
| `tm.UncertaintyResult` | Scalar estimate and propagated uncertainty with method provenance. |
| `tm.UncertaintyError` | Raised when uncertainty inputs or equation evaluations are invalid. |
