"""One-shot composition of the 0.1 engineering analysis steps."""

from __future__ import annotations

from dataclasses import dataclass

from .health import HealthAssessment, assess
from .modal import ModalResult, identify
from .sensors import SensorData
from .structure import Structure
from .update import update


@dataclass(frozen=True)
class MonitoringResult:
    structure: Structure
    modal: ModalResult
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


def monitor(structure: Structure, sensors: SensorData) -> MonitoringResult:
    """Run modal identification, uniform model update, then health comparison."""
    modal_result = identify(sensors)
    updated_structure = update(structure, modal_result)
    health_result = assess(structure=updated_structure, observations=sensors, modal_result=modal_result)
    return MonitoringResult(structure=updated_structure, modal=modal_result, health=health_result)
