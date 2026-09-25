"""Cross-section properties for common, prismatic sections (SI units)."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class SectionProperties:
    area_m2: float
    second_moment_y_m4: float
    second_moment_z_m4: float
    section_modulus_y_m3: float
    section_modulus_z_m3: float


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return value


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
