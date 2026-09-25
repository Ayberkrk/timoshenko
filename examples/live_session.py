"""Feed synthetic batches into a bounded-memory Timoshenko session."""

from __future__ import annotations

import math

import timoshenko as tm


def main() -> None:
    sampling_hz = 100.0
    sample_count = 768
    structure = tm.Structure(
        structure_id="demo-bridge",
        story_masses_kg=[120_000.0],
        story_stiffness_n_m=[85_000_000.0],
    )
    session = tm.MonitoringSession(
        structure,
        sensor_ids=["deck-left", "deck-right"],
        units=["m/s^2", "m/s^2"],
        sampling_hz=sampling_hz,
        window_samples=512,
        hop_samples=256,
        analysis_options={"nperseg": 256, "max_modes": 3},
    )

    origin = 1_800_000_000.0
    for batch_number, start in enumerate(range(0, sample_count, 64), start=1):
        observations = []
        for index in range(start, min(start + 64, sample_count)):
            t = index / sampling_hz
            left = math.sin(2.0 * math.pi * 5.0 * t) + 0.2 * math.sin(2.0 * math.pi * 12.0 * t)
            right = 0.7 * math.sin(2.0 * math.pi * 5.0 * t) - 0.4 * math.sin(2.0 * math.pi * 12.0 * t)
            timestamp = origin + t
            observations.extend((
                tm.Observation("deck-left", "acceleration", "m/s^2", left, timestamp=timestamp),
                tm.Observation("deck-right", "acceleration", "m/s^2", right, timestamp=timestamp),
            ))
        result = session.ingest(tm.ObservationBatch(
            observations,
            batch_id=f"demo:{batch_number}",
            source_id="synthetic-demo",
        ))
        for report in result.reports:
            print(report.to_dict())


if __name__ == "__main__":
    main()
