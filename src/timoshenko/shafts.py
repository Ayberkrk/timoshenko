"""Elastic Saint-Venant torsion formulas for circular prismatic shafts."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CircularTorsionResult:
    polar_moment_m4: float
    maximum_shear_stress_pa: float
    twist_rad: float


def circular_shaft_torsion(torque_nm: float, length_m: float, shear_modulus_pa: float,
                           outer_diameter_m: float, inner_diameter_m: float = 0.0) -> CircularTorsionResult:
    """Return elastic outer-fiber shear stress and twist for a round shaft.

    The shaft is prismatic and circular, with constant torque and linear
    isotropic elastic behavior. An inner diameter of zero describes a solid
    shaft. Non-circular sections and restrained warping are not covered.
    """
    torque, length = float(torque_nm), float(length_m)
    shear = float(shear_modulus_pa)
    outer, inner = float(outer_diameter_m), float(inner_diameter_m)
    if not all(math.isfinite(v) for v in (torque, length, shear, outer, inner)):
        raise ValueError("all inputs must be finite")
    if length <= 0.0 or shear <= 0.0 or outer <= 0.0 or inner < 0.0 or inner >= outer:
        raise ValueError("length, shear modulus, and outer diameter must be positive; inner diameter must be in [0, outer)")
    polar = math.pi * (outer**4 - inner**4) / 32.0
    return CircularTorsionResult(
        polar_moment_m4=polar,
        maximum_shear_stress_pa=torque * (outer / 2.0) / polar,
        twist_rad=torque * length / (shear * polar),
    )
