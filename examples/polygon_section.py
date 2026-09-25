"""Compute geometric properties of a polygonal hollow section."""

import timoshenko as tm


# A 200 x 300 mm outer rectangle with a 100 x 180 mm rectangular void.
section = tm.polygon_section(
    outer=[(0.0, 0.0), (0.20, 0.0), (0.20, 0.30), (0.0, 0.30)],
    holes=[[(0.05, 0.06), (0.15, 0.06), (0.15, 0.24), (0.05, 0.24)]],
)

print(section)
print("Centroid (m):", section.centroid_x_m, section.centroid_y_m)
print("Ixy (m^4):", section.product_moment_xy_m4)
