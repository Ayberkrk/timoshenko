"""Transparent, deliberately constrained modal model update."""

from __future__ import annotations

import math
import statistics

from .modal import ModalResult, pair_modes
from .oma import FDDResult
from .structure import Structure


def update(structure: Structure, modal: ModalResult | FDDResult) -> Structure:
    """Scale all story stiffnesses uniformly to fit identified frequencies.

    The scale is the median of ``(measured / analytical frequency) ** 2``
    across modes paired by :func:`timoshenko.modal.pair_modes`. This follows
    the uniform-stiffness relation ``f proportional to sqrt(k/m)``. It accepts
    single-channel FFT or multi-channel FDD modal results. It cannot localize
    damage or update stories independently. The scale is relative to the
    stiffness of ``structure`` as passed in.
    """
    if not isinstance(structure, Structure):
        raise TypeError("structure must be a timoshenko.Structure")
    if not isinstance(modal, (ModalResult, FDDResult)):
        raise TypeError("modal must be a result from tm.modal.identify() or tm.modal.identify_fdd()")
    if modal.status != "ok" or not modal.modes:
        raise ValueError(f"cannot update structure from modal result with status {modal.status!r}")

    analytical = structure.natural_frequencies_hz
    pairs = pair_modes(analytical, modal.frequencies_hz)
    scale_by_mode = [
        (modal.modes[observed].frequency_hz / analytical[reference]) ** 2
        for reference, observed in pairs
    ]
    if not scale_by_mode or any(not math.isfinite(scale) or scale <= 0.0 for scale in scale_by_mode):
        raise ValueError("modal/model frequency pairing produced an invalid stiffness scale")
    scale = float(statistics.median(scale_by_mode))
    spread_pct = 100.0 * statistics.median(abs(value - scale) for value in scale_by_mode) / scale
    status = "updated" if len(pairs) == structure.story_count else "updated_partial_modes"
    return structure.with_update(
        stiffness_scale=scale,
        observed_frequencies_hz=[modal.modes[observed].frequency_hz for _, observed in pairs],
        mode_scale_spread_pct=spread_pct,
        status=status,
    )
