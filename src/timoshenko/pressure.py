"""Thin-wall closed-cylinder membrane stress estimates."""

from __future__ import annotations

from dataclasses import dataclass

from ._validation import finite, positive


@dataclass(frozen=True)
class ThinWallCylinderResult:
    hoop_stress_pa: float
    longitudinal_stress_pa: float
    thickness_to_mean_radius_ratio: float

    def to_dict(self) -> dict[str, float]:
        return {
            "hoop_stress_pa": float(self.hoop_stress_pa),
            "longitudinal_stress_pa": float(self.longitudinal_stress_pa),
            "thickness_to_mean_radius_ratio": float(self.thickness_to_mean_radius_ratio),
        }


def thin_wall_cylinder_stress(
    pressure_difference_pa: float, mean_radius_m: float, wall_thickness_m: float
) -> ThinWallCylinderResult:
    """Estimate membrane stresses in a closed-end thin cylindrical vessel.

    The input is the inside-minus-outside pressure. The approximation assumes
    a circular, thin, closed-ended cylinder and membrane behavior; local end,
    nozzle, instability, fatigue, code, and thick-wall effects are excluded.
    """
    pressure = finite("pressure_difference_pa", pressure_difference_pa)
    radius = positive("mean_radius_m", mean_radius_m)
    thickness = positive("wall_thickness_m", wall_thickness_m)
    return ThinWallCylinderResult(
        hoop_stress_pa=pressure * radius / thickness,
        longitudinal_stress_pa=pressure * radius / (2.0 * thickness),
        thickness_to_mean_radius_ratio=thickness / radius,
    )
