"""Build and execute a small synthetic, two-channel project manifest."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import tempfile

import timoshenko as tm


def main() -> None:
    sampling_hz = 100.0
    duration_s = 40.0
    sample_count = int(sampling_hz * duration_s)
    structure = tm.Structure(
        structure_id="demo-two-story",
        story_masses_kg=[1_000.0, 800.0],
        story_stiffness_n_m=[500_000.0, 400_000.0],
    )
    first_hz, second_hz = structure.natural_frequencies_hz

    with tempfile.TemporaryDirectory(prefix="timoshenko-project-") as folder:
        root = Path(folder)
        csv_path = root / "accelerations.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("deck_lower", "deck_upper"))
            for index in range(sample_count):
                time_s = index / sampling_hz
                mode_1 = math.sin(2.0 * math.pi * first_hz * time_s)
                mode_2 = math.sin(2.0 * math.pi * second_hz * time_s)
                writer.writerow((mode_1 + 0.2 * mode_2, 0.5 * mode_1 - mode_2))

        manifest = {
            "schema_version": "1.0",
            "project": {"id": "two-story-demo", "name": "Two-story synthetic modal example"},
            "structure": {
                "type": "shear_building",
                "id": structure.structure_id,
                "story_masses_kg": list(structure.story_masses_kg),
                "story_stiffness_n_m": list(structure.story_stiffness_n_m),
            },
            "observations": {
                "file": csv_path.name,
                "sampling_hz": sampling_hz,
                "channels": [
                    {"column": "deck_lower", "id": "lower-floor-z", "unit": "m/s^2"},
                    {"column": "deck_upper", "id": "upper-floor-z", "unit": "m/s^2"},
                ],
            },
            "analysis": {"method": "fdd", "options": {"nperseg": 1024, "max_modes": 4}},
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        result = tm.run_project(manifest_path)

        print(f"Project: {result.project_name}")
        print(f"Method: {result.method}; evidence: {result.health.status}")
        print("Candidate frequencies (Hz):", ", ".join(f"{hz:.3f}" for hz in result.modal.frequencies_hz))
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
