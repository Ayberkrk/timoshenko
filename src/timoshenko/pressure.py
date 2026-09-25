"""Thin-wall closed-cylinder membrane stress estimates."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ThinWallCylinderResult:
    hoop_stress_pa: float
    longitudinal_stress_pa: float
    thickness_to_mean_radius_ratio: float


def thin_wall_cylinder_stress(pressure_difference_pa: float, mean_radius_m: float,
                              wall_thickness_m: float) -> ThinWallCylinderResult:
    """Estimate membrane stresses in a closed-end thin cylindrical vessel.

    The input is the inside-minus-outside pressure. The approximation assumes
    a circular, thin, closed-ended cylinder and membrane behavior; local end,
    nozzle, instability, fatigue, code, and thick-wall effects are excluded.
    """
    pressure, radius, thickness = map(float, (pressure_difference_pa, mean_radius_m, wall_thickness_m))
    if not all(math.isfinite(v) for v in (pressure, radius, thickness)):
        raise ValueError("inputs must be finite")
    if radius <= 0.0 or thickness <= 0.0:
        raise ValueError("mean radius and wall thickness must be positive")
    return ThinWallCylinderResult(
        hoop_stress_pa=pressure * radius / thickness,
        longitudinal_stress_pa=pressure * radius / (2.0 * thickness),
        thickness_to_mean_radius_ratio=thickness / radius,
    )
