"""Closed-form small-deflection beam responses for common load cases.

Euler-Bernoulli bending deflection is always reported. If both shear modulus
and cross-sectional area are supplied, a first-order shear-deflection term is
also returned (constant ``kappa`` shear-correction approximation).
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class BeamDeflection:
    bending_m: float
    shear_m: float

    @property
    def total_m(self) -> float:
        return self.bending_m + self.shear_m


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return value


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _response(bending: float, shear_force_factor: float, *, shear_modulus_pa: float | None,
              area_m2: float | None, shear_correction: float) -> BeamDeflection:
    if (shear_modulus_pa is None) != (area_m2 is None):
        raise ValueError("provide both shear_modulus_pa and area_m2 to include shear deflection")
    shear = 0.0
    if shear_modulus_pa is not None and area_m2 is not None:
        g = _positive("shear_modulus_pa", shear_modulus_pa)
        a = _positive("area_m2", area_m2)
        kappa = _positive("shear_correction", shear_correction)
        shear = shear_force_factor / (kappa * g * a)
    return BeamDeflection(float(bending), float(shear))


def cantilever_tip_load(load_n: float, span_m: float, youngs_modulus_pa: float,
                        second_moment_m4: float, *, shear_modulus_pa: float | None = None,
                        area_m2: float | None = None, shear_correction: float = 5.0 / 6.0) -> BeamDeflection:
    """Tip deflection of a cantilever with a point load at its free end."""
    p, length = _finite("load_n", load_n), _positive("span_m", span_m)
    e, inertia = _positive("youngs_modulus_pa", youngs_modulus_pa), _positive("second_moment_m4", second_moment_m4)
    return _response(p * length**3 / (3 * e * inertia), p * length,
                     shear_modulus_pa=shear_modulus_pa, area_m2=area_m2, shear_correction=shear_correction)


def cantilever_uniform_load(load_n_per_m: float, span_m: float, youngs_modulus_pa: float,
                            second_moment_m4: float, *, shear_modulus_pa: float | None = None,
                            area_m2: float | None = None, shear_correction: float = 5.0 / 6.0) -> BeamDeflection:
    """Free-end deflection of a cantilever under a full-span uniform load."""
    w, length = _finite("load_n_per_m", load_n_per_m), _positive("span_m", span_m)
    e, inertia = _positive("youngs_modulus_pa", youngs_modulus_pa), _positive("second_moment_m4", second_moment_m4)
    return _response(w * length**4 / (8 * e * inertia), w * length**2 / 2,
                     shear_modulus_pa=shear_modulus_pa, area_m2=area_m2, shear_correction=shear_correction)


def simply_supported_midpoint_load(load_n: float, span_m: float, youngs_modulus_pa: float,
                                   second_moment_m4: float, *, shear_modulus_pa: float | None = None,
                                   area_m2: float | None = None, shear_correction: float = 5.0 / 6.0) -> BeamDeflection:
    """Midspan deflection of a simply supported beam with a center point load."""
    p, length = _finite("load_n", load_n), _positive("span_m", span_m)
    e, inertia = _positive("youngs_modulus_pa", youngs_modulus_pa), _positive("second_moment_m4", second_moment_m4)
    return _response(p * length**3 / (48 * e * inertia), p * length / 4,
                     shear_modulus_pa=shear_modulus_pa, area_m2=area_m2, shear_correction=shear_correction)


def simply_supported_uniform_load(load_n_per_m: float, span_m: float, youngs_modulus_pa: float,
                                  second_moment_m4: float, *, shear_modulus_pa: float | None = None,
                                  area_m2: float | None = None, shear_correction: float = 5.0 / 6.0) -> BeamDeflection:
    """Midspan deflection of a simply supported beam under full-span UDL."""
    w, length = _finite("load_n_per_m", load_n_per_m), _positive("span_m", span_m)
    e, inertia = _positive("youngs_modulus_pa", youngs_modulus_pa), _positive("second_moment_m4", second_moment_m4)
    return _response(5 * w * length**4 / (384 * e * inertia), w * length**2 / 8,
                     shear_modulus_pa=shear_modulus_pa, area_m2=area_m2, shear_correction=shear_correction)
