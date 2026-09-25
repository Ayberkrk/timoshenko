"""Small, unit-explicit mechanics calculations for linear elastic materials.

All inputs use SI units. These functions calculate textbook quantities; they
do not perform code checks, resistance factors, or safety certification.
"""

from __future__ import annotations

import math

from ._validation import finite as _finite, positive as _positive


def axial_stress(force_n: float, area_m2: float) -> float:
    """Average normal stress ``N/A`` in pascals; tension is positive."""
    return _finite("force_n", force_n) / _positive("area_m2", area_m2)


def bending_stress(moment_nm: float, section_modulus_m3: float) -> float:
    """Extreme-fiber elastic bending stress ``M/S`` in pascals."""
    return _finite("moment_nm", moment_nm) / _positive("section_modulus_m3", section_modulus_m3)


def average_shear_stress(shear_n: float, area_m2: float) -> float:
    """Average shear stress ``V/A`` in pascals (not a peak-stress estimate)."""
    return _finite("shear_n", shear_n) / _positive("area_m2", area_m2)


def rectangular_max_shear_stress(shear_n: float, area_m2: float) -> float:
    """Maximum elastic shear stress ``1.5 V/A`` for a solid rectangle."""
    return 1.5 * average_shear_stress(shear_n, area_m2)


def axial_strain(stress_pa: float, youngs_modulus_pa: float) -> float:
    """Uniaxial elastic strain ``sigma/E`` (dimensionless)."""
    return _finite("stress_pa", stress_pa) / _positive("youngs_modulus_pa", youngs_modulus_pa)


def thermal_strain(expansion_per_k: float, temperature_change_k: float) -> float:
    """Free isotropic thermal strain ``alpha * delta_T`` (dimensionless)."""
    alpha = float(expansion_per_k)
    delta_t = float(temperature_change_k)
    if not math.isfinite(alpha) or not math.isfinite(delta_t):
        raise ValueError("thermal expansion coefficient and temperature change must be finite")
    return alpha * delta_t


def youngs_modulus_from_shear(shear_modulus_pa: float, poisson_ratio: float) -> float:
    """Return ``E = 2 G (1 + nu)`` for an isotropic linear elastic material."""
    shear = _positive("shear_modulus_pa", shear_modulus_pa)
    nu = float(poisson_ratio)
    if not math.isfinite(nu) or not -1.0 < nu < 0.5:
        raise ValueError("poisson_ratio must be finite and satisfy -1 < nu < 0.5")
    return 2.0 * shear * (1.0 + nu)
