"""Analytic area properties for simple polygonal cross-sections."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence

Point2D = tuple[float, float]
Ring = Sequence[Point2D]
_MAX_VERTICES = 512
_MAX_SPAN_M = 1e50


@dataclass(frozen=True)
class PolygonSectionProperties:
    """Geometric properties of a uniform polygonal section (SI units).

    ``second_moment_x_m4`` is about the centroidal x-axis (integral of y²),
    ``second_moment_y_m4`` is about the centroidal y-axis (integral of x²),
    and ``product_moment_xy_m4`` is the centroidal integral of x*y.
    Section moduli distinguish the positive and negative sides because a
    general polygon need not be symmetric about either centroidal axis.
    """

    area_m2: float
    centroid_x_m: float
    centroid_y_m: float
    second_moment_x_m4: float
    second_moment_y_m4: float
    product_moment_xy_m4: float
    section_modulus_x_positive_m3: float
    section_modulus_x_negative_m3: float
    section_modulus_y_positive_m3: float
    section_modulus_y_negative_m3: float


def polygon_section(
    outer: Ring,
    *,
    holes: Iterable[Ring] = (),
) -> PolygonSectionProperties:
    """Calculate area, centroid, second moments, product moment and moduli.

    Coordinates are ``(x, y)`` pairs in metres. The outer ring must describe a
    simple boundary; each optional hole must be a simple ring strictly inside
    it. Ring winding and explicit closure (repeating the first point) do not
    affect the result. Up to 512 total vertices are accepted.

    This computes uniform-density geometric properties only. It does not
    resolve stress under coupled bending, principal-axis design checks,
    material regions, plastic properties or torsion constants.
    """
    hole_rings = list(holes)
    rings = [_normalize_ring(outer, "outer")] + [
        _normalize_ring(ring, f"holes[{index}]") for index, ring in enumerate(hole_rings)
    ]
    if sum(map(len, rings)) > _MAX_VERTICES:
        raise ValueError(f"outer and hole rings may contain at most {_MAX_VERTICES} total vertices")

    origin_x, origin_y = rings[0][0]
    shifted = [[(x - origin_x, y - origin_y) for x, y in ring] for ring in rings]
    span = max(
        max(x for ring in shifted for x, _ in ring) - min(x for ring in shifted for x, _ in ring),
        max(y for ring in shifted for _, y in ring) - min(y for ring in shifted for _, y in ring),
    )
    if not math.isfinite(span) or span <= 0.0 or span > _MAX_SPAN_M:
        raise ValueError("polygon coordinate span must be finite, non-zero, and no greater than 1e50 m")

    area_tolerance = 1e-12 * span * span
    length_tolerance = 1e-12 * span
    for ring_index, ring in enumerate(shifted):
        _ensure_simple(ring, area_tolerance, length_tolerance, f"ring {ring_index}")
        if abs(_ring_integrals(ring)[0]) <= area_tolerance:
            raise ValueError(f"ring {ring_index} must enclose a non-zero area")
    _validate_holes(shifted, area_tolerance, length_tolerance)

    area = first_x = first_y = inertia_x_origin = inertia_y_origin = product_origin = 0.0
    for index, ring in enumerate(shifted):
        values = _ring_integrals(ring)
        signed_area = values[0]
        role = 1.0 if index == 0 else -1.0
        normalize = role if signed_area > 0.0 else -role
        area += normalize * values[0]
        first_x += normalize * values[1]
        first_y += normalize * values[2]
        inertia_x_origin += normalize * values[3]
        inertia_y_origin += normalize * values[4]
        product_origin += normalize * values[5]

    if not math.isfinite(area) or area <= area_tolerance:
        raise ValueError("outer ring and holes must leave a positive finite material area")
    cx_local, cy_local = first_x / area, first_y / area
    ixx = inertia_x_origin - area * cy_local**2
    iyy = inertia_y_origin - area * cx_local**2
    ixy = product_origin - area * cx_local * cy_local
    # Roundoff can make a theoretically zero product moment tiny and negative
    # inertias tiny around very slender geometries. Do not hide material errors.
    if not all(math.isfinite(v) for v in (cx_local, cy_local, ixx, iyy, ixy)):
        raise ValueError("polygon dimensions produced non-finite properties")
    if ixx <= 0.0 or iyy <= 0.0:
        raise ValueError("polygon dimensions produced non-positive centroidal second moments")

    min_x, max_x = min(x for x, _ in shifted[0]), max(x for x, _ in shifted[0])
    min_y, max_y = min(y for _, y in shifted[0]), max(y for _, y in shifted[0])
    distances = (max_y - cy_local, cy_local - min_y, max_x - cx_local, cx_local - min_x)
    if any(distance <= 0.0 or not math.isfinite(distance) for distance in distances):
        raise ValueError("polygon section must have positive extreme-fibre distances on every side")

    result_values = (
        area,
        origin_x + cx_local,
        origin_y + cy_local,
        ixx,
        iyy,
        ixy,
        ixx / distances[0],
        ixx / distances[1],
        iyy / distances[2],
        iyy / distances[3],
    )
    if not all(math.isfinite(value) for value in result_values):
        raise ValueError("polygon dimensions produced non-finite section properties")
    return PolygonSectionProperties(*result_values)


def _normalize_ring(ring: Ring, name: str) -> list[Point2D]:
    try:
        points = []
        for point in ring:
            if len(point) != 2:
                raise ValueError(f"{name} vertices must have exactly two coordinates")
            points.append((float(point[0]), float(point[1])))
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError(f"{name} must be an iterable of finite (x, y) coordinate pairs") from exc
    if len(points) > 1 and points[-1] == points[0]:
        points.pop()
    if len(points) < 3:
        raise ValueError(f"{name} must contain at least three distinct vertices")
    if any(not math.isfinite(x) or not math.isfinite(y) for x, y in points):
        raise ValueError(f"{name} coordinates must be finite")
    if any(points[index] == points[(index + 1) % len(points)] for index in range(len(points))):
        raise ValueError(f"{name} must not contain repeated consecutive vertices")
    return points


def _ring_integrals(ring: Sequence[Point2D]) -> tuple[float, float, float, float, float, float]:
    area2 = first_x6 = first_y6 = inertia_x12 = inertia_y12 = product24 = 0.0
    for (x0, y0), (x1, y1) in zip(ring, (*ring[1:], ring[0])):
        cross = x0 * y1 - x1 * y0
        area2 += cross
        first_x6 += (x0 + x1) * cross
        first_y6 += (y0 + y1) * cross
        inertia_x12 += (y0 * y0 + y0 * y1 + y1 * y1) * cross
        inertia_y12 += (x0 * x0 + x0 * x1 + x1 * x1) * cross
        product24 += (2*x0*y0 + x0*y1 + x1*y0 + 2*x1*y1) * cross
    return area2/2, first_x6/6, first_y6/6, inertia_x12/12, inertia_y12/12, product24/24


def _ensure_simple(ring: Sequence[Point2D], area_tolerance: float, length_tolerance: float, label: str) -> None:
    count = len(ring)
    for index in range(count):
        previous, current, following = ring[index - 1], ring[index], ring[(index + 1) % count]
        incoming = (previous[0] - current[0], previous[1] - current[1])
        outgoing = (following[0] - current[0], following[1] - current[1])
        cross = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
        dot = incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
        if abs(cross) <= area_tolerance and dot > length_tolerance**2:
            raise ValueError(f"{label} must not contain a backtracking overlapping edge")
    for first in range(count):
        a, b = ring[first], ring[(first + 1) % count]
        for second in range(first + 1, count):
            if second == first or second == (first + 1) % count or (second + 1) % count == first:
                continue
            c, d = ring[second], ring[(second + 1) % count]
            if _segments_intersect(a, b, c, d, area_tolerance, length_tolerance):
                raise ValueError(f"{label} must not self-intersect")


def _segments_intersect(
    a: Point2D,
    b: Point2D,
    c: Point2D,
    d: Point2D,
    area_tolerance: float,
    length_tolerance: float,
) -> bool:
    def orient(p: Point2D, q: Point2D, r: Point2D) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p: Point2D, q: Point2D, r: Point2D) -> bool:
        return (
            min(p[0], r[0]) - length_tolerance <= q[0] <= max(p[0], r[0]) + length_tolerance
            and min(p[1], r[1]) - length_tolerance <= q[1] <= max(p[1], r[1]) + length_tolerance
        )

    ab_c, ab_d, cd_a, cd_b = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if ((ab_c > area_tolerance and ab_d < -area_tolerance) or (ab_c < -area_tolerance and ab_d > area_tolerance)) and (
        (cd_a > area_tolerance and cd_b < -area_tolerance) or (cd_a < -area_tolerance and cd_b > area_tolerance)
    ):
        return True
    return (
        abs(ab_c) <= area_tolerance and on_segment(a, c, b)
        or abs(ab_d) <= area_tolerance and on_segment(a, d, b)
        or abs(cd_a) <= area_tolerance and on_segment(c, a, d)
        or abs(cd_b) <= area_tolerance and on_segment(c, b, d)
    )


def _point_in_ring(point: Point2D, ring: Sequence[Point2D]) -> bool:
    x, y = point
    inside = False
    previous = ring[-1]
    for current in ring:
        x0, y0 = previous
        x1, y1 = current
        if (y0 > y) != (y1 > y):
            crossing_x = (x1 - x0) * (y - y0) / (y1 - y0) + x0
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def _validate_holes(
    rings: Sequence[Sequence[Point2D]], area_tolerance: float, length_tolerance: float
) -> None:
    outer = rings[0]
    holes = rings[1:]
    for index, hole in enumerate(holes):
        if not _point_in_ring(hole[0], outer):
            raise ValueError(f"hole {index} must be strictly inside the outer ring")
        if _rings_intersect(hole, outer, area_tolerance, length_tolerance):
            raise ValueError(f"hole {index} must not touch or cross the outer ring")
        for earlier_index, earlier in enumerate(holes[:index]):
            if (
                _rings_intersect(hole, earlier, area_tolerance, length_tolerance)
                or _point_in_ring(hole[0], earlier)
                or _point_in_ring(earlier[0], hole)
            ):
                raise ValueError(f"holes {earlier_index} and {index} must not overlap or contain one another")


def _rings_intersect(
    first: Sequence[Point2D],
    second: Sequence[Point2D],
    area_tolerance: float,
    length_tolerance: float,
) -> bool:
    return any(
        _segments_intersect(a, b, c, d, area_tolerance, length_tolerance)
        for a, b in zip(first, (*first[1:], first[0]))
        for c, d in zip(second, (*second[1:], second[0]))
    )
