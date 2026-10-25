# Linear time-history response

`analyze_time_history` integrates a 2D `StructuralModel` or 3D
`StructuralModel3D` with Newmark's average-acceleration method
(`gamma=1/2`, `beta=1/4`). The model remains linear elastic and the support
conditions remain fixed throughout the record.

The time vector must have at least two finite, uniformly spaced values.
`force_history_n` is a finite matrix with one row per time sample and one
column per model degree of freedom: three degrees per node for a 2D model,
six for a 3D model. Components follow the global node order: `(Fx, Fy, Mz)` in
2D and `(Fx, Fy, Fz, Mx, My, Mz)` in 3D. A scalar `base_acceleration_m_s2`
record can be supplied in `direction="x"`, `"y"`, or (3D only) `"z"`; it is
converted to inertia loads with the assembled mass matrix. Direct forces and
base acceleration can be combined.

Optional `initial_displacements_m` and `initial_velocities_m_s` each contain
one value per model degree of freedom in the same node order. Values at
restrained degrees of freedom must be zero because moving supports are not
modeled.

Rayleigh damping uses `C = alpha M + beta K`, configured with
`rayleigh_mass_per_s` and `rayleigh_stiffness_s`. The returned result contains
displacement, velocity, acceleration and reaction histories at all nodes, plus
free-degree residual norms. At zero-mass free coordinates, initial acceleration
is reported as zero; later acceleration values are recovered from the
integrated displacement history.

When `base_acceleration_m_s2` is supplied, the returned displacement,
velocity and acceleration histories are relative to the moving base. Convert
the acceleration to absolute sensor acceleration by adding the ground
acceleration in the selected translational direction:
`a_absolute = a_relative + a_ground`. The result does not add a separate
absolute-acceleration field.

The average-acceleration scheme is unconditionally stable for a linear system,
but that does not guarantee accurate peaks or phase: choose the time step to
resolve the highest response frequency of interest. The solver does not
support time-varying support movement, nonlinear material or geometric
response, inelastic damping, or adaptive time stepping. Verify the model and
time-step sensitivity against an analytical oscillator or independent solver.
