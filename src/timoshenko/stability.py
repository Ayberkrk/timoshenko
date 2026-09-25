"""Ideal elastic column stability formulas (not member design checks)."""

from __future__ import annotations

import math


def euler_critical_load(youngs_modulus_pa: float, second_moment_m4: float,
                        length_m: float, effective_length_factor: float = 1.0) -> float:
    """Euler elastic critical load ``pi^2 E I / (K L)^2`` in newtons.

    The caller selects ``K`` for the actual restraint and buckling axis.
    ``K=1`` is the ideal pin-pin case. The equation assumes a straight,
    prismatic, slender, perfectly elastic column with ideal axial loading.
    """
    e, inertia, length, factor = map(float, (youngs_modulus_pa, second_moment_m4, length_m, effective_length_factor))
    if not all(math.isfinite(v) and v > 0.0 for v in (e, inertia, length, factor)):
        raise ValueError("E, I, length, and effective length factor must be finite and positive")
    effective_length = factor * length
    return math.pi**2 * e * inertia / effective_length**2


def slenderness_ratio(length_m: float, effective_length_factor: float,
                      area_m2: float, second_moment_m4: float) -> float:
    """Geometric slenderness ``K L / r_g`` for one selected buckling axis."""
    length, factor, area, inertia = map(float, (length_m, effective_length_factor, area_m2, second_moment_m4))
    if not all(math.isfinite(v) and v > 0.0 for v in (length, factor, area, inertia)):
        raise ValueError("length, factor, area, and second moment must be finite and positive")
    radius_gyration = math.sqrt(inertia / area)
    return factor * length / radius_gyration
