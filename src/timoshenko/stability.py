"""Ideal elastic column stability formulas (not member design checks)."""

from __future__ import annotations

import math

from ._validation import positive


def euler_critical_load(
    youngs_modulus_pa: float,
    second_moment_m4: float,
    length_m: float,
    effective_length_factor: float = 1.0,
) -> float:
    """Euler elastic critical load ``pi^2 E I / (K L)^2`` in newtons.

    The caller selects ``K`` for the actual restraint and buckling axis.
    ``K=1`` is the ideal pin-pin case. The equation assumes a straight,
    prismatic, slender, perfectly elastic column with ideal axial loading.
    """
    e = positive("youngs_modulus_pa", youngs_modulus_pa)
    inertia = positive("second_moment_m4", second_moment_m4)
    length = positive("length_m", length_m)
    factor = positive("effective_length_factor", effective_length_factor)
    effective_length = factor * length
    return math.pi**2 * e * inertia / effective_length**2


def slenderness_ratio(
    length_m: float, effective_length_factor: float, area_m2: float, second_moment_m4: float
) -> float:
    """Geometric slenderness ``K L / r_g`` for one selected buckling axis."""
    length = positive("length_m", length_m)
    factor = positive("effective_length_factor", effective_length_factor)
    area = positive("area_m2", area_m2)
    inertia = positive("second_moment_m4", second_moment_m4)
    radius_gyration = math.sqrt(inertia / area)
    return factor * length / radius_gyration
