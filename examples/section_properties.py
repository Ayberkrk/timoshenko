"""Calculate idealized I-section and rectangular-tube properties."""

import timoshenko as tm


steel_i = tm.i_section(
    overall_width_m=0.20,
    overall_height_m=0.30,
    web_thickness_m=0.010,
    flange_thickness_m=0.015,
)
box = tm.rectangular_tube_section(
    outer_width_m=0.20,
    outer_height_m=0.30,
    wall_thickness_m=0.008,
)

print("Idealized I-section:", steel_i)
print("Idealized rectangular tube:", box)
