"""One-shot composition of the 0.1 engineering analysis steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .health import HealthAssessment, assess
from .modal import ModalResult, identify
from .multichannel import MultiChannelData
from .oma import FDDResult, identify_fdd
from .sensors import SensorData
from .structure import Structure
from .update import update


@dataclass(frozen=True)
class MonitoringResult:
    structure: Structure
    modal: ModalResult | FDDResult
    health: HealthAssessment

    def to_dict(self) -> dict:
        return {
            "structure": {
                "structure_id": self.structure.structure_id,
                "story_count": self.structure.story_count,
                "natural_frequencies_hz": list(self.structure.natural_frequencies_hz),
                "reference_frequencies_hz": list(self.structure.baseline_frequencies_hz),
                "observed_frequencies_hz": list(self.structure.observed_frequencies_hz),
                "update_scale_factor": self.structure.update_scale_factor,
                "update_mode_count": self.structure.update_mode_count,
                "update_mode_scale_spread_pct": self.structure.update_mode_scale_spread_pct,
                "update_status": self.structure.update_status,
            },
            "modal": self.modal.to_dict(),
            "health": self.health.to_dict(),
        }


def monitor(
    structure: Structure,
    sensors: SensorData | MultiChannelData,
    *,
    review_threshold_pct: float | None = None,
    **analysis_options: Any,
) -> MonitoringResult:
    """Identify modes, update the reference model, and compare its baseline.

    Single-channel data uses ``modal.identify``; aligned multi-channel data
    uses ``identify_fdd``. Extra keyword options are passed to that estimator.
    """
    modal_result: ModalResult | FDDResult
    if isinstance(sensors, SensorData):
        modal_result = identify(sensors, **analysis_options)
    elif isinstance(sensors, MultiChannelData):
        modal_result = identify_fdd(sensors, **analysis_options)
    else:
        raise TypeError("sensors must be SensorData or MultiChannelData")
    updated_structure = update(structure, modal_result) if modal_result.modes else structure
    health_result = assess(
        structure=updated_structure,
        observations=sensors,
        modal_result=modal_result,
        review_threshold_pct=review_threshold_pct,
    )
    return MonitoringResult(structure=updated_structure, modal=modal_result, health=health_result)
