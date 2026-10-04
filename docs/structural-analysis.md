# 2D frame analysis

``tm.StructuralModel`` assembles prismatic two-node axial bars and frame
members in a plane. Each node has global x and y translation and rotation
about z. Supply support restraints, optional prescribed movements at
restrained degrees of freedom, one set of nodal loads, and member loads in
local coordinates. Coordinates are metres; forces are newtons; moments are
newton metres; material properties use pascals.

```python
import timoshenko as tm

steel = tm.FrameMaterial(youngs_modulus_pa=200e9, shear_modulus_pa=77e9)
section = tm.rectangle_section(width_m=0.08, height_m=0.16)
beam_section = tm.FrameSection(
    area_m2=section.area_m2,
    second_moment_local_z_m4=section.second_moment_z_m4,
)
model = tm.StructuralModel(
    nodes=[tm.FrameNode(0.0, 0.0), tm.FrameNode(4.0, 0.0)],
    members=[tm.FrameMember(0, 1, steel, beam_section)],
    restraints=[(True, True, True), (False, False, False)],
    nodal_loads=[(0.0, 0.0, 0.0), (0.0, -10_000.0, 0.0)],
)
result = tm.analyze_linear_static(model)
print(result.displacements[1])
print(result.reactions[0])
```

The local frame x axis points from member node i to node j. Local y is the
in-plane transverse axis. ``FrameSection.second_moment_local_z_m4`` therefore
means the second moment for bending in the frame plane. If an effective local
shear area is supplied, the static member stiffness uses Timoshenko shear
flexibility. With no shear area, bending uses Euler-Bernoulli kinematics.
Shear area is explicit because the engine does not derive it from an arbitrary
outline. Uniform load components and ``FramePointLoad`` forces are positive
along local x and local y. A point moment is positive about local z. Axial bars
support local axial loads and do not use bending section data. Rotational end
releases are condensed from frame-member stiffness and load vectors.
Modal and buckling analyses keep each released member-end rotation as an
internal degree of freedom, separate from the joint rotation. P-delta analysis
also solves with internal released-end rotations, then reports only joint
displacements.

The frame section inertia is about a principal local z axis. Coupled bending
and out-of-plane torsion from an unsymmetric section are not assembled into
this planar model. ``FrameMaterial.poisson_ratio`` is optional; when supplied,
the engine checks that E and G agree with isotropic elasticity within 0.2
percent. Member point forces and point moments are converted to nodal loads
with the shape functions of the member stiffness, including its shear
parameter when a shear area is supplied, so a loaded member gives the same
nodal response as the same member split at the load.

The result reports three displacement components per node, support reactions,
local member end actions ordered as axial force, shear force, moment at node i
then node j, strain energy and the free-degree equilibrium residual. The
analysis is a single linear load case. Combine loads and factors before
analysis when superposition applies. Supply both local-y section moduli on
``FrameSection`` to request end normal stresses. The stress order is positive-y
then negative-y at node i, followed by positive-y then negative-y at node j.
Axial bars return uniform axial stress at both fibers. Stress capacity is not
checked. ``global_equilibrium_residual`` reports the total force and moment
resultant left by loads and support reactions; for P-delta results the moment
is evaluated at the displaced nodal positions.

``tm.analyze_p_delta`` iterates an approximate geometric stiffness from the
average axial force in each member. It reports the same result fields with
``analysis_type="p_delta"`` and an iteration count. Tensile force adds
geometric stiffness and compression reduces it. The geometric stiffness uses
Euler-Bernoulli interpolation, even if material bending stiffness uses
Timoshenko shear flexibility. It is a first-order P-delta approximation for
stability screening, not a nonlinear equilibrium path or a design resistance
calculation.

P-delta and linear buckling analyses support frame-member end releases,
including pinned-base columns. Released member-end rotations remain independent
of joint rotations in both analyses.

## Frame modes

``tm.analyze_modes`` assembles consistent member translational mass from
``mass_per_length_kg_m`` and adds nodal lumped mass to each translational
degree of freedom. Its member mass interpolation is Euler-Bernoulli, member
rotary inertia is omitted, and restraints are removed before solving the
generalized eigenproblem. It returns frequencies, mode shapes normalized to
unit peak translation, generalized mass, directional participation factors,
effective modal mass and effective modal mass ratio in global x and y. A
released member-end rotation is an internal degree of freedom with the member's
consistent mass; the returned mode shape still contains the three joint
components at each node. A mode calculation needs positive mass on every free
component. Compare measured and analytical shapes with
``tm.modal_assurance_criterion`` after mapping the measured degrees of freedom
into the same order.

For direction vector ``r``, modal participation is
``Gamma = phi.T @ M @ r / (phi.T @ M @ phi)`` and effective modal mass is
``Gamma**2 * (phi.T @ M @ phi)``. The reported ratio divides this by the total
free mass participating in that direction. Ratios depend on which degrees of
freedom the caller leaves active.

``tm.analyze_linear_buckling`` calculates elastic system buckling factors for
one reference load pattern. It obtains member axial forces from the first
order solution and solves an eigenvalue problem for the proportional load
factor. Refine the member mesh and compare against a classical solution for
the chosen boundary conditions. This ideal bifurcation estimate omits
initial imperfections, material yielding and post-buckling response. The
reference member axial force output is positive in tension and negative in
compression.

## Result serialization

Static, P-delta, modal and buckling results provide `to_dict()`. The returned
dictionary has the same fields as the result, with tuples converted to lists,
so it can be written with `json.dumps`. Member end stresses that were not
requested stay `None`.

```python
import json

result = tm.analyze_linear_static(model)
text = json.dumps(result.to_dict())
```

## Scope and checks

The initial solver covers small-displacement, linear-elastic, planar trusses
and frames with prismatic members, ideal supports, nodal and member point
loads, uniform member loads, and prescribed support movements. It does not
calculate code combinations, section capacity, nonlinear equilibrium paths,
nonlinear material response, 3D frames, plates or shells. It reports elastic
response and does not make a safety finding.

The frame routines are checked against cantilever closed-form displacement,
Timoshenko shear deflection, point-load and uniform-load reactions, prescribed
support movement, released ends, axial-bar response, portal equilibrium,
modal participation and buckling mesh refinement, including pinned-pinned and
fixed-pinned columns. For safety-related work,
verify each model's signs, local axes, boundary conditions, mesh adequacy and
assumptions against an independent engineering reference.

The elastic frame inputs and coordinate transformation follow the same
parameter separation used by the [OpenSees Elastic Timoshenko Beam Column
Element](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/elements/ElasticTimoshenkoBeamColumnElement.html).
The tests in this repository check analytic solutions and mesh convergence;
they do not by themselves establish suitability for a measured structure.
The recommended distinction between code verification, solution verification
and validation follows [NASA-HDBK-7009](https://standards.nasa.gov/sites/default/files/standards/NASA/A/0/Historical/nasa-hdbk-7009.pdf).
