"""Replay a long-format sensor CSV through Timoshenko's monitoring session."""

from __future__ import annotations

import argparse
import json

import timoshenko as tm


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="long-format observation CSV")
    parser.add_argument("--sensor-id", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--sample-rate", type=float, required=True, help="samples per second")
    parser.add_argument("--source-id", default=None)
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    structure = tm.Structure(
        structure_id="csv-replay",
        story_masses_kg=[100_000.0],
        story_stiffness_n_m=[20_000_000.0],
    )
    session = tm.MonitoringSession(
        structure,
        sensor_ids=[args.sensor_id],
        units=[args.unit],
        sampling_hz=args.sample_rate,
        window_samples=256,
    )
    source = tm.CSVObservationSource(
        args.csv_path,
        source_id=args.source_id,
        batch_size=args.batch_size,
    )

    with tm.SessionRunner(source, session) as runner:
        for result in runner:
            print(json.dumps(result.to_dict(), ensure_ascii=False))


if __name__ == "__main__":
    main()
