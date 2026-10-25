# Linear 3D truss and frame analysis

The separate `StructuralModel3D` API assembles small, prismatic 3D truss and
frame models. It does not change the existing 2D `StructuralModel` contract.
Coordinates are metres, forces newtons, moments newton-metres, mass kilograms,
and material properties use SI units.

```python
import timoshenko as tm

steel = tm.FrameMaterial3D(youngs_modulus_pa=200e9, shear_modulus_pa=77e9)
section = tm.FrameSection3D(
    area_m2=0.01,
    second_moment_y_m4=8e-6,
    second_moment_z_m4=8e-6,
    torsion_constant_m4=1e-5,
)
model = tm.StructuralModel3D(
    nodes=(tm.FrameNode3D(0, 0, 0), tm.FrameNode3D(0, 0, 3)),
    members=(tm.FrameMember3D(0, 1, steel, section, local_y_reference=(0, 1, 0)),),
    restraints=((True, True, True, True, True, True), (False,) * 6),
    nodal_loads=((0,) * 6, (0, 0, -10_000, 0, 0, 0)),
)
static = tm.analyze_linear_static_3d(model)
modal = tm.analyze_modes_3d(model)
```

Each frame member's local x axis runs from node i to node j. Its local-y
reference vector is projected into the plane perpendicular to local x; the
right-handed local z axis is their cross product. The vector must not be
parallel to the member axis. The default reference `(0, 1, 0)` is suitable for
most horizontal members; choose an explicit reference for vertical or
otherwise aligned members. `FrameMaterial3D` accepts Young's and shear moduli;
an optional Poisson ratio validates their isotropic consistency. Frame
stiffness uses Euler-Bernoulli bending, elastic axial stiffness and
Saint-Venant torsion. The model uses six degrees of freedom per node in
`(ux, uy, uz, rx, ry, rz)` order.

`analyze_linear_static_3d` solves one nodal load case and returns node
displacements, support reactions, strain energy and the free-degree residual.
`analyze_modes_3d` solves the undamped generalized eigenproblem. Member and
nodal mass are lumped to translational degrees of freedom; rotary inertia is
omitted. Zero-mass rotations are statically condensed for modal analysis and
recovered in the mode shapes. A free truss rotation has no stiffness and must
be restrained.

`analyze_linear_buckling_3d` estimates ideal proportional elastic buckling
factors from a first-order nodal load pattern. It uses axial member force and
Euler-Bernoulli beam-column geometric stiffness. It does not model
imperfections, yielding, post-buckling, code resistance, distributed/member
loads, end releases, prescribed support movements, shear deformation, or
non-prismatic members. These results are screening calculations, not a safety
finding. Check signs, orientation, boundary conditions, mesh adequacy and
results against independent engineering references before project use.

The first 3D release uses dense NumPy matrices intended for small models. It is
not a sparse large-scale finite-element solver and does not include plates,
shells, contact or nonlinear material response.
