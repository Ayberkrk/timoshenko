import dataclasses
import math

import numpy as np
import pytest

import timoshenko as tm


def rectangle(x0, y0, width, height):
    return [(x0, y0), (x0 + width, y0), (x0 + width, y0 + height), (x0, y0 + height)]


def test_rectangle_matches_section_formula_and_is_translation_invariant():
    reference = tm.rectangle_section(0.3, 0.6)
    for origin in ((0.0, 0.0), (1.0e6, -2.5e6)):
        result = tm.polygon_section(rectangle(*origin, 0.3, 0.6))
        assert result.area_m2 == pytest.approx(reference.area_m2, rel=1e-9)
        assert result.second_moment_x_m4 == pytest.approx(reference.second_moment_y_m4, rel=1e-6)
        assert result.second_moment_y_m4 == pytest.approx(reference.second_moment_z_m4, rel=1e-6)
        assert result.product_moment_xy_m4 == pytest.approx(0.0, abs=1e-9)
        assert result.centroid_x_m == pytest.approx(origin[0] + 0.15)
        assert result.centroid_y_m == pytest.approx(origin[1] + 0.3)


def test_right_triangle_centroid_and_product_moment():
    b, h = 0.6, 0.9
    result = tm.polygon_section([(0.0, 0.0), (b, 0.0), (0.0, h)])
    assert result.area_m2 == pytest.approx(b * h / 2)
    assert (result.centroid_x_m, result.centroid_y_m) == pytest.approx((b / 3, h / 3))
    assert result.second_moment_x_m4 == pytest.approx(b * h**3 / 36)
    assert result.second_moment_y_m4 == pytest.approx(h * b**3 / 36)
    assert result.product_moment_xy_m4 == pytest.approx(-(b**2) * h**2 / 72)
    assert result.section_modulus_x_positive_m3 == pytest.approx(result.second_moment_x_m4 / (2 * h / 3))
    assert result.section_modulus_x_negative_m3 == pytest.approx(result.second_moment_x_m4 / (h / 3))


def test_winding_and_explicit_closure_do_not_change_result():
    ring = rectangle(0.0, 0.0, 0.4, 0.2)
    forward = dataclasses.astuple(tm.polygon_section(ring))
    assert dataclasses.astuple(tm.polygon_section(ring[::-1])) == pytest.approx(forward, abs=1e-15)
    assert dataclasses.astuple(tm.polygon_section(ring + [ring[0]])) == pytest.approx(forward, abs=1e-15)


def test_hollow_rectangle_matches_rectangular_tube():
    b, h, t = 0.15, 0.25, 0.008
    tube = tm.rectangular_tube_section(b, h, t)
    result = tm.polygon_section(rectangle(0, 0, b, h), holes=[rectangle(t, t, b - 2 * t, h - 2 * t)[::-1]])
    assert result.area_m2 == pytest.approx(tube.area_m2)
    assert result.second_moment_x_m4 == pytest.approx(tube.second_moment_y_m4)
    assert result.second_moment_y_m4 == pytest.approx(tube.second_moment_z_m4)


def test_i_section_outline_matches_i_section_formula():
    b, h, tw, tf = 0.2, 0.4, 0.01, 0.015
    x1, x2 = (b - tw) / 2, (b + tw) / 2
    outline = [(0, 0), (b, 0), (b, tf), (x2, tf), (x2, h - tf), (b, h - tf), (b, h),
               (0, h), (0, h - tf), (x1, h - tf), (x1, tf), (0, tf)]
    reference = tm.i_section(b, h, tw, tf)
    result = tm.polygon_section(outline)
    assert result.area_m2 == pytest.approx(reference.area_m2)
    assert result.second_moment_x_m4 == pytest.approx(reference.second_moment_y_m4)
    assert result.second_moment_y_m4 == pytest.approx(reference.second_moment_z_m4)


def test_rotation_preserves_principal_moments():
    base = tm.polygon_section(rectangle(0, 0, 0.5, 0.1))
    theta = math.radians(27.0)
    c, s = math.cos(theta), math.sin(theta)
    rotated = tm.polygon_section([(c * x - s * y, s * x + c * y) for x, y in rectangle(0, 0, 0.5, 0.1)])
    tensor = np.array([[rotated.second_moment_x_m4, rotated.product_moment_xy_m4],
                       [rotated.product_moment_xy_m4, rotated.second_moment_y_m4]])
    principal = sorted(np.linalg.eigvalsh(tensor))
    assert principal == pytest.approx(sorted([base.second_moment_x_m4, base.second_moment_y_m4]), rel=1e-9)


def test_regular_polygon_converges_to_circle():
    radius, sides = 0.2, 500
    ring = [(radius * math.cos(2 * math.pi * i / sides), radius * math.sin(2 * math.pi * i / sides)) for i in range(sides)]
    result = tm.polygon_section(ring)
    assert result.second_moment_x_m4 == pytest.approx(math.pi * radius**4 / 4, rel=1e-3)
    assert result.product_moment_xy_m4 == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize(
    "outer, holes",
    [
        ([(0, 0), (1, 1), (1, 0), (0, 1)], ()),
        ([(0, 0), (1, 0), (2, 0)], ()),
        (rectangle(0, 0, 1, 1), [rectangle(0.5, 0.5, 1, 1)]),
        (rectangle(0, 0, 1, 1), [rectangle(2, 2, 0.1, 0.1)]),
        (rectangle(0, 0, 1, 1), [rectangle(0.1, 0.1, 0.3, 0.3), rectangle(0.2, 0.2, 0.3, 0.3)]),
        ([(0, 0), (1, 0), (1, 0), (0, 1)], ()),
    ],
    ids=["bowtie", "collinear", "hole-crosses", "hole-outside", "holes-overlap", "repeated-vertex"],
)
def test_invalid_geometry_is_rejected(outer, holes):
    with pytest.raises(ValueError):
        tm.polygon_section(outer, holes=holes)


def test_vertex_limit():
    ring = [(math.cos(2 * math.pi * i / 513), math.sin(2 * math.pi * i / 513)) for i in range(513)]
    with pytest.raises(ValueError):
        tm.polygon_section(ring)
