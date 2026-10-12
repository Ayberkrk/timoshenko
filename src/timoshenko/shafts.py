"""Elastic Saint-Venant torsion formulas for circular prismatic shafts."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ._validation import finite, positive


@dataclass(frozen=True)
class CircularTorsionResult:
    polar_moment_m4: float
    maximum_shear_stress_pa: float
    twist_rad: float

    def to_dict(self) -> dict[str, float]:
        return {
            "polar_moment_m4": float(self.polar_moment_m4),
            "maximum_shear_stress_pa": float(self.maximum_shear_stress_pa),
            "twist_rad": float(self.twist_rad),
        }


def circular_shaft_torsion(
    torque_nm: float,
    length_m: float,
    shear_modulus_pa: float,
    outer_diameter_m: float,
    inner_diameter_m: float = 0.0,
) -> CircularTorsionResult:
    """Return elastic outer-fiber shear stress and twist for a round shaft.

    The shaft is prismatic and circular, with constant torque and linear
    isotropic elastic behavior. An inner diameter of zero describes a solid
    shaft. Non-circular sections and restrained warping are not covered.
    """
    torque = finite("torque_nm", torque_nm)
    length = positive("length_m", length_m)
    shear = positive("shear_modulus_pa", shear_modulus_pa)
    outer = positive("outer_diameter_m", outer_diameter_m)
    inner = finite("inner_diameter_m", inner_diameter_m)
    if inner < 0.0:
        raise ValueError("inner_diameter_m must be non-negative")
    if inner >= outer:
        raise ValueError("inner_diameter_m must be smaller than outer_diameter_m")
    polar = math.pi * (outer**4 - inner**4) / 32.0
    return CircularTorsionResult(
        polar_moment_m4=polar,
        maximum_shear_stress_pa=torque * (outer / 2.0) / polar,
        twist_rad=torque * length / (shear * polar),
    )
