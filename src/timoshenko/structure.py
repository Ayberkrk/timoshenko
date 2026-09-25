"""Simple structural models used by Timoshenko's first release.

Version 0.1 implements a linear lumped-mass shear-building model. It is a
reference model for modal comparison, not a general purpose FEM solver.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class Structure:
    """A shear-building model with one lateral degree of freedom per floor.

    ``story_masses_kg[i]`` and ``story_stiffness_n_m[i]`` describe floor i,
    ordered from the base upward. Supply a measured baseline frequency list
    when an analytical model baseline is not available.
    """

    story_masses_kg: tuple[float, ...] | Sequence[float]
    story_stiffness_n_m: tuple[float, ...] | Sequence[float]
    structure_id: str = "structure"
    name: str = ""
    reference_frequencies_hz: tuple[float, ...] = ()
    observed_frequencies_hz: tuple[float, ...] = ()
    update_scale_factor: float | None = None
    update_mode_count: int = 0
    update_mode_scale_spread_pct: float | None = None
    update_status: str = "not_updated"

    def __post_init__(self) -> None:
        masses = tuple(float(value) for value in self.story_masses_kg)
        stiffnesses = tuple(float(value) for value in self.story_stiffness_n_m)
        if not masses or len(masses) != len(stiffnesses):
            raise ValueError("story_masses_kg and story_stiffness_n_m must have the same non-zero length")
        if any(not math.isfinite(value) or value <= 0.0 for value in masses):
            raise ValueError("story masses must be finite positive values in kilograms")
        if any(not math.isfinite(value) or value <= 0.0 for value in stiffnesses):
            raise ValueError("story stiffnesses must be finite positive values in newtons per metre")
        reference = tuple(float(value) for value in self.reference_frequencies_hz)
        observed = tuple(float(value) for value in self.observed_frequencies_hz)
        for label, values in (("reference", reference), ("observed", observed)):
            if any(not math.isfinite(value) or value <= 0.0 for value in values):
                raise ValueError(f"{label} modal frequencies must be finite positive values")
        if reference and len(reference) > len(masses):
            raise ValueError("reference_frequencies_hz cannot contain more entries than the number of stories")
        if observed and len(observed) > len(masses):
            raise ValueError("observed_frequencies_hz cannot contain more entries than the number of stories")
        object.__setattr__(self, "story_masses_kg", masses)
        object.__setattr__(self, "story_stiffness_n_m", stiffnesses)
        object.__setattr__(self, "reference_frequencies_hz", reference)
        object.__setattr__(self, "observed_frequencies_hz", observed)

    @property
    def story_count(self) -> int:
        return len(self.story_masses_kg)

    @property
    def natural_frequencies_hz(self) -> tuple[float, ...]:
        """Return analytical frequencies for the undamped shear model."""
        n = self.story_count
        stiffness = np.zeros((n, n), dtype=float)
        for floor, story_k in enumerate(self.story_stiffness_n_m):
            stiffness[floor, floor] += story_k
            if floor > 0:
                stiffness[floor - 1, floor - 1] += story_k
                stiffness[floor, floor - 1] -= story_k
                stiffness[floor - 1, floor] -= story_k
        inv_sqrt_mass = np.diag(1.0 / np.sqrt(np.asarray(self.story_masses_kg, dtype=float)))
        mass_normalized = inv_sqrt_mass @ stiffness @ inv_sqrt_mass
        eigenvalues = np.linalg.eigvalsh(mass_normalized)
        frequencies = np.sqrt(np.maximum(eigenvalues, 0.0)) / (2.0 * math.pi)
        return tuple(float(value) for value in frequencies if value > 0.0)

    @property
    def baseline_frequencies_hz(self) -> tuple[float, ...]:
        """Explicit reference frequencies, or the model's analytical modes."""
        return self.reference_frequencies_hz or self.natural_frequencies_hz

    def with_update(
        self,
        *,
        stiffness_scale: float,
        observed_frequencies_hz: Sequence[float],
        mode_scale_spread_pct: float,
        status: str,
    ) -> "Structure":
        reference = self.reference_frequencies_hz or self.natural_frequencies_hz
        return replace(
            self,
            story_stiffness_n_m=tuple(k * stiffness_scale for k in self.story_stiffness_n_m),
            reference_frequencies_hz=reference,
            observed_frequencies_hz=tuple(float(f) for f in observed_frequencies_hz),
            update_scale_factor=float(stiffness_scale),
            update_mode_count=len(observed_frequencies_hz),
            update_mode_scale_spread_pct=float(mode_scale_spread_pct),
            update_status=status,
        )
