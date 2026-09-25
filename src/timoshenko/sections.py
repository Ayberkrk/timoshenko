"""Cross-section properties for common, prismatic sections (SI units)."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ._validation import positive as _positive
# Re-exported so the general polygon helper is also reachable as tm.sections.polygon_section.
from .polygon import PolygonSectionProperties, polygon_section  # noqa: F401


@dataclass(frozen=True)
class SectionProperties:
    area_m2: float
    second_moment_y_m4: float
    second_moment_z_m4: float
    section_modulus_y_m3: float
    section_modulus_z_m3: float


def rectangle(width_m: float, height_m: float) -> SectionProperties:
    """Return centroidal properties; y is the width axis, z the height axis."""
    b, h = _positive("width_m", width_m), _positive("height_m", height_m)
    area = b * h
    iy, iz = b * h**3 / 12.0, h * b**3 / 12.0
    return SectionProperties(area, iy, iz, iy / (h / 2.0), iz / (b / 2.0))


def solid_circle(diameter_m: float) -> SectionProperties:
    """Return centroidal properties for a solid circular section."""
    d = _positive("diameter_m", diameter_m)
    area = math.pi * d**2 / 4.0
    inertia = math.pi * d**4 / 64.0
    modulus = inertia / (d / 2.0)
    return SectionProperties(area, inertia, inertia, modulus, modulus)


def circular_tube(outer_diameter_m: float, inner_diameter_m: float) -> SectionProperties:
    """Return centroidal properties for a concentric circular hollow section."""
    outer = _positive("outer_diameter_m", outer_diameter_m)
    inner = float(inner_diameter_m)
    if not math.isfinite(inner) or inner < 0.0 or inner >= outer:
        raise ValueError("inner_diameter_m must be finite, non-negative, and smaller than outer diameter")
    area = math.pi * (outer**2 - inner**2) / 4.0
    inertia = math.pi * (outer**4 - inner**4) / 64.0
    modulus = inertia / (outer / 2.0)
    return SectionProperties(area, inertia, inertia, modulus, modulus)


def i_section(
    overall_width_m: float,
    overall_height_m: float,
    web_thickness_m: float,
    flange_thickness_m: float,
) -> SectionProperties:
    """Return centroidal properties of an ideal symmetric sharp-corner I-section.

    The web is centered and joins two identical rectangular flanges. Fillets,
    flange taper, and manufacturing tolerances are not included.
    """
    width = _positive("overall_width_m", overall_width_m)
    height = _positive("overall_height_m", overall_height_m)
    web = _positive("web_thickness_m", web_thickness_m)
    flange = _positive("flange_thickness_m", flange_thickness_m)
    if web >= width:
        raise ValueError("web_thickness_m must be smaller than overall_width_m")
    if 2.0 * flange >= height:
        raise ValueError("twice flange_thickness_m must be smaller than overall_height_m")
    web_height = height - 2.0 * flange
    flange_offset = (height - flange) / 2.0
    area = 2.0 * width * flange + web * web_height
    inertia_y = (
        2.0 * (width * flange**3 / 12.0 + width * flange * flange_offset**2)
        + web * web_height**3 / 12.0
    )
    inertia_z = 2.0 * flange * width**3 / 12.0 + web_height * web**3 / 12.0
    return _checked_properties(area, inertia_y, inertia_z, height / 2.0, width / 2.0)


def rectangular_tube(
    outer_width_m: float,
    outer_height_m: float,
    wall_thickness_m: float,
) -> SectionProperties:
    """Return centroidal properties of an ideal uniform-wall rectangular tube.

    The shape has sharp corners and constant wall thickness. Corner radii,
    weld geometry, and manufacturing tolerances are not included.
    """
    width = _positive("outer_width_m", outer_width_m)
    height = _positive("outer_height_m", outer_height_m)
    thickness = _positive("wall_thickness_m", wall_thickness_m)
    if 2.0 * thickness >= min(width, height):
        raise ValueError("twice wall_thickness_m must be smaller than both outer dimensions")
    inner_height = height - 2.0 * thickness
    inner_width = width - 2.0 * thickness
    horizontal_plate_offset = (height - thickness) / 2.0
    vertical_plate_offset = (width - thickness) / 2.0
    area = 2.0 * width * thickness + 2.0 * thickness * inner_height
    inertia_y = (
        2.0 * (width * thickness**3 / 12.0 + width * thickness * horizontal_plate_offset**2)
        + 2.0 * thickness * inner_height**3 / 12.0
    )
    inertia_z = (
        2.0 * thickness * width**3 / 12.0
        + 2.0 * (inner_height * thickness**3 / 12.0 + inner_height * thickness * vertical_plate_offset**2)
    )
    return _checked_properties(area, inertia_y, inertia_z, height / 2.0, width / 2.0)


def _checked_properties(area: float, inertia_y: float, inertia_z: float, half_height: float, half_width: float) -> SectionProperties:
    values = (area, inertia_y, inertia_z, half_height, half_width)
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise ValueError("section dimensions produced non-finite or non-positive geometric properties")
    modulus_y, modulus_z = inertia_y / half_height, inertia_z / half_width
    if not math.isfinite(modulus_y) or not math.isfinite(modulus_z):
        raise ValueError("section dimensions produced non-finite section moduli")
    return SectionProperties(area, inertia_y, inertia_z, modulus_y, modulus_z)
