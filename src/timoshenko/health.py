"""Evidence-oriented modal health comparison."""

from __future__ import annotations

from dataclasses import dataclass

from .modal import ModalResult, identify
from .sensors import SensorData
from .structure import Structure


@dataclass(frozen=True)
class ModeChange:
    mode_number: int
    reference_frequency_hz: float
    observed_frequency_hz: float
    change_pct: float


@dataclass(frozen=True)
class HealthAssessment:
    structure_id: str
    status: str
    mode_changes: tuple[ModeChange, ...]
    modal_result: ModalResult
    review_recommended: bool
    evidence_summary: str
    limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "structure_id": self.structure_id,
            "status": self.status,
            "mode_changes": [
                {
                    "mode_number": item.mode_number,
                    "reference_frequency_hz": item.reference_frequency_hz,
                    "observed_frequency_hz": item.observed_frequency_hz,
                    "change_pct": item.change_pct,
                }
                for item in self.mode_changes
            ],
            "modal_result": self.modal_result.to_dict(),
            "review_recommended": self.review_recommended,
            "evidence_summary": self.evidence_summary,
            "limitations": list(self.limitations),
        }


def assess(
    *,
    structure: Structure,
    observations: SensorData,
    modal_result: ModalResult | None = None,
) -> HealthAssessment:
    """Compare observed frequencies with the structure's preserved baseline.

    This reports measured changes only. Release 0.1 does not assign a safety
    category, probability of failure, or action threshold.
    """
    if not isinstance(structure, Structure):
        raise TypeError("structure must be a timoshenko.Structure")
    if not isinstance(observations, SensorData):
        raise TypeError("observations must be a timoshenko.SensorData")
    result = modal_result or identify(observations)
    reference = structure.baseline_frequencies_hz
    paired = min(len(reference), len(result.modes))
    changes = tuple(
        ModeChange(
            mode_number=idx + 1,
            reference_frequency_hz=float(reference[idx]),
            observed_frequency_hz=float(result.modes[idx].frequency_hz),
            change_pct=100.0 * (float(result.modes[idx].frequency_hz) - float(reference[idx])) / float(reference[idx]),
        )
        for idx in range(paired)
    )
    enough = result.status == "ok" and paired > 0
    status = "evidence_available" if enough else "insufficient_evidence"
    summary = (
        f"Compared {paired} observed mode(s) with the reference model."
        if enough
        else "No usable modal frequency could be compared with the reference model."
    )
    notes = (
        "Frequency shifts can have several causes, including temperature, boundary conditions, sensor placement, and structural change.",
        "This assessment is not a diagnosis of damage or a statement of structural safety.",
    )
    return HealthAssessment(
        structure_id=structure.structure_id,
        status=status,
        mode_changes=changes,
        modal_result=result,
        review_recommended=any(change.change_pct < 0.0 for change in changes),
        evidence_summary=summary,
        limitations=notes,
    )
