"""Plane-stress transformations for homogeneous linear elasticity."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PlaneStressResult:
    principal_max_pa: float
    principal_min_pa: float
    maximum_in_plane_shear_pa: float
    von_mises_pa: float


def plane_stress(sigma_x_pa: float, sigma_y_pa: float, tau_xy_pa: float) -> PlaneStressResult:
    """Return principal stresses, in-plane max shear, and plane-stress von Mises.

    The third principal stress is assumed zero (plane stress). No material
    yield criterion, failure probability, or allowable stress is applied.
    """
    sx, sy, txy = map(float, (sigma_x_pa, sigma_y_pa, tau_xy_pa))
    if not all(math.isfinite(v) for v in (sx, sy, txy)):
        raise ValueError("stress components must be finite")
    center = (sx + sy) / 2.0
    radius = math.hypot((sx - sy) / 2.0, txy)
    von_mises = math.sqrt(max(0.0, sx**2 - sx * sy + sy**2 + 3.0 * txy**2))
    return PlaneStressResult(center + radius, center - radius, radius, von_mises)
