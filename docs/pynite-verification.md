# Verifying PyNite shear-deformable members

[PyNite](https://github.com/JWock82/Pynite) is an open-source 3D structural
finite element library for Python by D. Craig Brinck, released under the MIT
license. Support for shear-deformable (Timoshenko-Ehrenfest) beam members was
contributed by jrrifareal in
[PyNite pull request #289](https://github.com/JWock82/Pynite/pull/289) and is
being reviewed on PyNite's `shear_deformation` branch before it reaches a
PyNite release.

The example `examples/pynite_shear_beam.py` builds three beams in PyNite and
compares its nodal results with closed-form values composed from Timoshenko
functions. It shows how Timoshenko's calculations can serve as an independent
check on a finite element model. PyNite is not a Timoshenko dependency.

## Run it

```bash
python -m pip install timoshenko-engine
python -m pip install "PyNiteFEA @ git+https://github.com/JWock82/Pynite@shear_deformation"
python examples/pynite_shear_beam.py
```

## What it compares

A 0.2 m by 0.6 m glulam-like rectangle with E = 11 GPa and G = 0.69 GPa
(E/G = 16) spans 3 m. The shear correction factor is the conventional 5/6 for
a solid rectangle; for the dependence of this factor on Poisson's ratio and on
its definition, see [Cowper (1966)](https://doi.org/10.1115/1.3625046) and the
[literature review](literature-review.md).

| Quantity | PyNite | Timoshenko | Bending only |
|---|---:|---:|---:|
| Cantilever tip deflection under 10 kN [mm] | 2.7075 | 2.7075 | 2.2727 |
| Simply supported midspan deflection under 5 kN/m [mm] | 0.2147 | 0.2147 | 0.1332 |
| Propped cantilever prop reaction under 5 kN/m [kN] | 5.9261 | 5.9261 | 5.6250 |

The Timoshenko column adds the shear term to the Euler-Bernoulli bending term,
using `tm.cantilever_tip_load`, `tm.simply_supported_uniform_load`, and
`tm.cantilever_uniform_load`. The propped cantilever is statically
indeterminate: its prop reaction follows from compatibility at the prop, using
the cantilever deflection under the load divided by the deflection under a unit
tip force. The "bending only" column shows the result when shear deformation is
ignored; for this section the midspan deflection is about 60% larger with shear.

## Limits

- The comparison uses nodal displacements and reactions, which agree to
  floating-point precision. On the `shear_deformation` branch, deflections read
  between nodes with `member.deflection()` still follow the Euler-Bernoulli
  shape and omit the shear term; this is documented with tests in
  [PyNite pull request #341](https://github.com/JWock82/Pynite/pull/341). Place
  a node where a deflection is needed until that is resolved.
- Closed-form solutions apply to prismatic, linear elastic members with the
  stated supports and loads. They verify the element formulation, not a
  particular structure or a design check.
