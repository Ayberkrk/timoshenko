# Polygon section properties

`tm.polygon_section(outer, holes=...)` calculates uniform-material geometric
properties from simple closed polygon boundaries. Each vertex is `(x, y)` in
metres. The first ring bounds material; optional rings remove holes. Rings may
be clockwise or counter-clockwise and can omit or repeat the closing vertex.
The outer and all hole rings together may contain at most 512 vertices.

For each edge `i -> i+1`, including the final-to-first edge, define
`c_i = x_i y_(i+1) - x_(i+1) y_i`. Signed boundary sums give area and first
moments:

```text
A   = 1/2 sum(c_i)
Qx  = 1/6 sum((x_i + x_(i+1)) c_i)
Qy  = 1/6 sum((y_i + y_(i+1)) c_i)
Cx  = Qx / A
Cy  = Qy / A
```

The corresponding origin area moments and product moment are:

```text
Ixx0 = 1/12 sum((y_i² + y_i y_(i+1) + y_(i+1)²) c_i)
Iyy0 = 1/12 sum((x_i² + x_i x_(i+1) + x_(i+1)²) c_i)
Ixy0 = 1/24 sum((2 x_i y_i + x_i y_(i+1)
                   + x_(i+1) y_i + 2 x_(i+1) y_(i+1)) c_i)
Ixx  = Ixx0 - A Cy²
Iyy  = Iyy0 - A Cx²
Ixy  = Ixy0 - A Cx Cy
```

The result returns `Ixx` about the centroidal x-axis, `Iyy` about the
centroidal y-axis, and signed `Ixy`. Hole boundary sums are subtracted after
normalizing their winding direction, so input ring orientation does not alter
the physical result. Directional elastic moduli are `Ixx / c` or `Iyy / c`
using separate extreme-fibre distances on each side of each centroidal axis.

The implementation rejects non-finite/repeated adjacent coordinates,
self-intersecting rings, holes that touch or leave the outer boundary,
overlapping/nested holes, zero-area rings, and non-positive resulting material
area. Coordinates are translated close to the section before integration to
reduce cancellation for sections specified far from the origin.

This is a 2D geometric integration, not a structural resistance calculation.
It does not compute principal axes, stress under unsymmetric/coupled bending,
plastic section moduli, shear area, torsion constant, local buckling, material
regions, or code checks. A general polygon's product moment may be non-zero;
using either axis inertia alone in an uncoupled bending formula may therefore
be inappropriate. The equations are based on Green's theorem / shoelace
polygon integrals ([Bourke, 1988](https://paulbourke.net/geometry/polygonmesh/));
composite section subtraction and parallel-axis context is summarized in
[Engineering Statics](https://engineeringstatics.org/Chapter_10-moment-of-inertia-of-composite-shapes.html).
