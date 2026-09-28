# 2D frame analysis

``tm.StructuralModel`` assembles prismatic two-node members in a planar frame.
Each node has global x and y translation and rotation about z. Supply support
restraints, one set of nodal loads, and any uniform member loads in local
coordinates. Coordinates are metres; forces are newtons; moments are newton
metres; material properties use pascals.

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
outline. Uniform load components are positive along local x and local y.

The result reports three displacement components per node, support reactions,
local member end actions ordered as axial force, shear force, moment at node i
then node j, strain energy and the free-degree equilibrium residual. The
analysis is a single linear load case. Combine loads and factors before
analysis when superposition applies.

``tm.analyze_p_delta`` iterates an approximate geometric stiffness from the
average axial force in each member. It reports the same result fields with
``analysis_type="p_delta"`` and an iteration count. Tensile force adds
geometric stiffness and compression reduces it. The geometric stiffness uses
Euler-Bernoulli interpolation, even if material bending stiffness uses
Timoshenko shear flexibility. It is a first-order P-delta approximation for
stability screening, not a nonlinear equilibrium path or a design resistance
calculation.

## Frame modes

``tm.analyze_modes`` assembles consistent member translational mass from
``mass_per_length_kg_m`` and adds nodal lumped mass to each translational
degree of freedom. Its member mass interpolation is Euler-Bernoulli, member
rotary inertia is omitted, and restraints are removed before solving the
generalized eigenproblem. It returns frequencies, mode shapes normalized to
unit peak translation, and each returned shape's generalized mass. A mode
calculation needs positive mass on every free component.

## Scope and checks

The initial solver covers small-displacement, linear-elastic, planar frames
with prismatic members, ideal supports, nodal loads and uniform member loads.
It does not calculate code combinations, section capacity, nonlinear
equilibrium paths, nonlinear material response, 3D frames, plates or shells.
It reports elastic response and does not make a safety finding.

The frame routines are checked against cantilever closed-form displacement,
Timoshenko shear deflection, simply supported uniform-load reactions, member
rotation, and a one-element axial generalized eigenvalue. For safety-related
work, verify each model's signs, local axes, boundary conditions, mesh
adequacy and assumptions against an independent engineering reference.
