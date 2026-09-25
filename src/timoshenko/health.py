"""Evidence-oriented modal health comparison."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .modal import ModalResult, identify, pair_modes
from .multichannel import MultiChannelData
from .oma import FDDResult, identify_fdd
from .sensors import SensorData
from .structure import Structure


@dataclass(frozen=True)
class ModeChange:
    """One observed mode compared with the reference mode it was paired to.

    ``mode_number`` is the 1-based reference mode and ``observed_mode_number``
    the 1-based position in the modal result. A change no larger than the
    spectral resolution is ``resolution_limited``: its sign and size are set
    by the frequency grid, not by the structure.
    """

    mode_number: int
    reference_frequency_hz: float
    observed_frequency_hz: float
    change_pct: float
    observed_mode_number: int = 0
    resolution_limited: bool = False


@dataclass(frozen=True)
class HealthAssessment:
    structure_id: str
    status: str
    mode_changes: tuple[ModeChange, ...]
    modal_result: ModalResult | FDDResult
    review_recommended: bool
    evidence_summary: str
    limitations: tuple[str, ...]
    review_threshold_pct: float | None = None

    def to_dict(self) -> dict:
        return {
            "structure_id": self.structure_id,
            "status": self.status,
            "mode_changes": [
                {
                    "mode_number": item.mode_number,
                    "observed_mode_number": item.observed_mode_number,
                    "reference_frequency_hz": item.reference_frequency_hz,
                    "observed_frequency_hz": item.observed_frequency_hz,
                    "change_pct": item.change_pct,
                    "resolution_limited": item.resolution_limited,
                }
                for item in self.mode_changes
            ],
            "modal_result": self.modal_result.to_dict(),
            "review_recommended": self.review_recommended,
            "review_threshold_pct": self.review_threshold_pct,
            "evidence_summary": self.evidence_summary,
            "limitations": list(self.limitations),
        }


def validate_review_threshold(value: float | None) -> float | None:
    """Return a finite positive review threshold in percent, or ``None``."""
    if value is None:
        return None
    threshold = float(value)
    if not math.isfinite(threshold) or threshold <= 0.0:
        raise ValueError("review_threshold_pct must be finite and greater than zero, or None")
    return threshold


def assess(
    *,
    structure: Structure,
    observations: SensorData | MultiChannelData,
    modal_result: ModalResult | FDDResult | None = None,
    review_threshold_pct: float | None = None,
) -> HealthAssessment:
    """Compare observed frequencies with the structure's preserved baseline.

    Observed modes are paired with reference modes by nearest frequency (see
    :func:`timoshenko.modal.pair_modes`). ``review_recommended`` is raised
    only when the caller supplies ``review_threshold_pct`` and a paired mode
    drops by at least that percentage by more than the spectral resolution.
    The engine does not choose that threshold: a meaningful value depends on
    the asset, its environmental variability, and a calibrated baseline.
    No safety category or probability of failure is assigned.
    """
    if not isinstance(structure, Structure):
        raise TypeError("structure must be a timoshenko.Structure")
    if not isinstance(observations, (SensorData, MultiChannelData)):
        raise TypeError("observations must be SensorData or MultiChannelData")
    threshold = validate_review_threshold(review_threshold_pct)
    if modal_result is not None:
        result = modal_result
    elif isinstance(observations, SensorData):
        result = identify(observations)
    else:
        result = identify_fdd(observations)
    if not isinstance(result, (ModalResult, FDDResult)):
        raise TypeError("modal_result must be a ModalResult or FDDResult")
    reference = structure.baseline_frequencies_hz
    pairs = pair_modes(reference, result.frequencies_hz)
    changes = []
    for reference_index, observed_index in pairs:
        reference_hz = float(reference[reference_index])
        observed_hz = float(result.modes[observed_index].frequency_hz)
        changes.append(ModeChange(
            mode_number=reference_index + 1,
            reference_frequency_hz=reference_hz,
            observed_frequency_hz=observed_hz,
            change_pct=100.0 * (observed_hz - reference_hz) / reference_hz,
            observed_mode_number=observed_index + 1,
            resolution_limited=abs(observed_hz - reference_hz) <= result.resolution_hz,
        ))
    enough = result.status == "ok" and bool(changes)
    status = "evidence_available" if enough else "insufficient_evidence"
    summary = (
        f"Compared {len(changes)} observed mode(s) with the reference model."
        if enough
        else "No usable modal frequency could be compared with the reference model."
    )
    notes = [
        "Frequency shifts can have several causes, including temperature, boundary conditions, sensor placement, and structural change.",
        "This assessment is not a diagnosis of damage or a statement of structural safety.",
    ]
    unpaired = len(result.modes) - len(changes)
    if unpaired:
        notes.append(f"{unpaired} observed peak(s) were not paired with a reference mode and were not compared.")
    if threshold is None:
        notes.append("No review threshold was supplied, so no review flag is raised; choose one from a calibrated baseline.")
    review = threshold is not None and any(
        not change.resolution_limited and change.change_pct <= -threshold for change in changes
    )
    return HealthAssessment(
        structure_id=structure.structure_id,
        status=status,
        mode_changes=tuple(changes),
        modal_result=result,
        review_recommended=review,
        evidence_summary=summary,
        limitations=tuple(notes),
        review_threshold_pct=threshold,
    )
