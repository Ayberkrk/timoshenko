# Idealized I-section and rectangular tube (1.8)

`tm.sections.i_section` and `tm.sections.rectangular_tube` calculate cross
section area, both centroidal second moments, and elastic section moduli. The
same functions are available at top level as `tm.i_section(...)` and
`tm.rectangular_tube_section(...)`.

All inputs use SI metres. The centroid is at the geometric center for both
symmetric shapes. `second_moment_y_m4` is about the horizontal centroidal axis
and therefore uses the vertical dimension cubed; `second_moment_z_m4` is about
the vertical centroidal axis and uses the width cubed.

## Symmetric sharp-corner I-section

Let overall width be `b`, overall height `h`, web thickness `tw`, and flange
thickness `tf`, with `tw < b` and `2 tf < h`. The web height is `h-2 tf`:

```text
A   = 2 b tf + tw (h - 2 tf)
Iy  = 2 [b tf^3/12 + b tf ((h - tf)/2)^2] + tw (h - 2 tf)^3/12
Iz  = 2 tf b^3/12 + (h - 2 tf) tw^3/12
Wy  = Iy / (h/2)
Wz  = Iz / (b/2)
```

## Uniform-wall rectangular tube

Let outer width be `b`, outer height be `h`, and uniform wall thickness be `t`,
with `2 t < min(b, h)`. Define inner height `hi=h-2t`:

```text
A   = 2 b t + 2 t hi
Iy  = 2 [b t^3/12 + b t ((h - t)/2)^2] + 2 t hi^3/12
Iz  = 2 t b^3/12 + 2 [hi t^3/12 + hi t ((b - t)/2)^2]
Wy  = Iy / (h/2)
Wz  = Iz / (b/2)
```

The formulas treat the section as rectangles with sharp corners. They do not
include fillets, corner radii, welds, taper, variable wall thickness,
manufacturing tolerances, local buckling, shear area, plastic modulus, torsion
constant, material strength, or code checks. The [AISC Shapes Database](https://www.aisc.org/aisc/publications/steel-construction-manual/aisc-shapes-database-v160/)
provides dimensions and published properties for standard and historic
structural shapes; use the published table when a named manufactured section
is required. These equations are geometric primitives, not a replacement for
that catalog data.
