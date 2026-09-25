"""Cross-check PyNite shear-deformable members with Timoshenko closed-form results.

PyNite (https://github.com/JWock82/Pynite, MIT license, (c) D. Craig Brinck)
is a 3D finite element library. Support for shear-deformable (Timoshenko
beam) members was contributed in PyNite pull request #289 and currently lives
on its ``shear_deformation`` branch, so install PyNite from that branch:

    python -m pip install "PyNiteFEA @ git+https://github.com/JWock82/Pynite@shear_deformation"

The script builds three timber beams in PyNite and compares nodal results
with closed-form values assembled from Timoshenko functions. PyNite is not a
Timoshenko dependency; it is only needed to run this example.
"""

import inspect
import math

import timoshenko as tm

try:
    from Pynite import FEModel3D
except ImportError:
    raise SystemExit(
        "This example needs PyNite with shear-deformable members:\n"
        '  python -m pip install "PyNiteFEA @ git+https://github.com/JWock82/Pynite@shear_deformation"'
    ) from None

if "shear_deformable" not in inspect.signature(FEModel3D.add_member).parameters:
    raise SystemExit("The installed PyNite has no shear_deformable option; install its shear_deformation branch.")

# Glulam-like rectangle. E/G = 16 makes the shear term a visible share of the result.
E, G, NU = 11e9, 0.69e9, 0.3
section = tm.rectangle_section(width_m=0.2, height_m=0.6)
KAPPA = 5 / 6                       # shear correction factor of a solid rectangle
SPAN, POINT_LOAD, LINE_LOAD = 3.0, 10e3, 5e3
SHEAR = dict(shear_modulus_pa=G, area_m2=section.area_m2, shear_correction=KAPPA)
I_STRONG = section.second_moment_y_m4  # Timoshenko y axis is the width axis, i.e. bending of the height


def pynite_model(node_positions):
    model = FEModel3D()
    model.add_material("Glulam", E, G, NU, 0.0)
    # PyNite's Iz is the strong axis and ksy pairs with it.
    model.add_section("Rect", section.area_m2, section.second_moment_z_m4, I_STRONG, 3.33e-3, ksy=KAPPA, ksz=KAPPA)
    names = [f"N{index + 1}" for index in range(len(node_positions))]
    for name, x in zip(names, node_positions):
        model.add_node(name, x, 0, 0)
    for index, (start, end) in enumerate(zip(names, names[1:]), start=1):
        model.add_member(f"M{index}", start, end, "Glulam", "Rect", shear_deformable=True)
    return model


rows = []

# 1. Cantilever with a tip load: deflection at the free end.
model = pynite_model([0.0, SPAN])
model.def_support("N1", True, True, True, True, True, True)
model.add_node_load("N2", "FY", -POINT_LOAD)
model.analyze()
expected = tm.cantilever_tip_load(POINT_LOAD, SPAN, E, I_STRONG, **SHEAR)
rows.append(("Cantilever tip deflection [mm]", -model.nodes["N2"].DY["Combo 1"] * 1e3, expected.total_m * 1e3, expected.bending_m * 1e3))

# 2. Simply supported span under a uniform load: deflection at a midspan node.
model = pynite_model([0.0, SPAN / 2, SPAN])
model.def_support("N1", True, True, True, True, False, False)
model.def_support("N3", False, True, True, False, False, False)
for member in ("M1", "M2"):
    model.add_member_dist_load(member, "Fy", -LINE_LOAD, -LINE_LOAD)
model.analyze()
expected = tm.simply_supported_uniform_load(LINE_LOAD, SPAN, E, I_STRONG, **SHEAR)
rows.append(("Simply supported midspan deflection [mm]", -model.nodes["N2"].DY["Combo 1"] * 1e3, expected.total_m * 1e3, expected.bending_m * 1e3))

# 3. Propped cantilever under a uniform load: the prop reaction is statically
# indeterminate, so it follows from compatibility at the prop using two
# Timoshenko cantilever solutions (load alone, and a unit tip force).
model = pynite_model([0.0, SPAN])
model.def_support("N1", True, True, True, True, True, True)
model.def_support("N2", False, True, True, False, False, False)
model.add_member_dist_load("M1", "Fy", -LINE_LOAD, -LINE_LOAD)
model.analyze()
released = tm.cantilever_uniform_load(LINE_LOAD, SPAN, E, I_STRONG, **SHEAR)
unit_tip = tm.cantilever_tip_load(1.0, SPAN, E, I_STRONG, **SHEAR)
prop_total = released.total_m / unit_tip.total_m
prop_bending_only = released.bending_m / unit_tip.bending_m
rows.append(("Propped cantilever prop reaction [kN]", model.nodes["N2"].RxnFY["Combo 1"] / 1e3, prop_total / 1e3, prop_bending_only / 1e3))

print(f"{'Quantity':44s} {'PyNite':>10s} {'Timoshenko':>11s} {'Bending only':>13s}")
for label, pynite_value, closed_form, bending_only in rows:
    print(f"{label:44s} {pynite_value:10.4f} {closed_form:11.4f} {bending_only:13.4f}")
    assert math.isclose(pynite_value, closed_form, rel_tol=1e-9), label

print(
    "\nPyNite nodal results match the closed-form Timoshenko values. Deflections read between\n"
    "nodes with member.deflection() on PyNite's shear_deformation branch omit the shear term;\n"
    "see https://github.com/JWock82/Pynite/pull/341."
)
