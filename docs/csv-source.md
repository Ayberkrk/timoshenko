# CSV observation replay

`CSVObservationSource` replays long-format sensor data through the same
`ObservationSource` and `SessionRunner` interfaces used by protocol adapters.
It reads at most one configured batch into memory and uses only Python's
standard library.

## CSV schema

The default header is:

```csv
timestamp,sensor_id,name,unit,value,quality,asset_id
2026-09-25T09:00:00Z,accel-01,Deck acceleration,m/s^2,0.012,true,bridge-01
```

Required columns by default: `timestamp`, `sensor_id`, `unit`, and `value`.
`name`, `quality`, and `asset_id` are optional columns; when configured, their
headers must exist. Set a column option to `None` to omit `name`, `quality`, or
`asset_id`. With no `name` column, the sensor ID is used as the observation
name. With no quality column, each row is marked good.

Timestamps accept Unix seconds or timezone-aware ISO-8601. Naive local times,
empty required values, non-finite numbers, duplicate headers, and rows with
more fields than the header raise `CSVSourceError`. Values stay in the unit
provided by the CSV; no unit conversion, resampling, interpolation, sorting, or
column-name guessing is performed. Rows are consumed in file order.

Batch size is configurable from 1 to 4096 rows. Stable batch IDs are generated
from `source_id` and the inclusive range of non-empty data rows, so changing
batch size does not reuse an ID for different row contents. Replay through a
`SQLiteStore` can use its existing duplicate protection. Supply your own `source_id` when you
need a stable identity across renaming or relocating a file; the default uses
the filename.

## Use with a monitoring session

```python
import timoshenko as tm

structure = tm.Structure(
    structure_id="bridge-01",
    story_masses_kg=[100_000],
    story_stiffness_n_m=[20_000_000],
)
session = tm.MonitoringSession(
    structure,
    sensor_ids=["accel-01"],
    units=["m/s^2"],
    sampling_hz=100.0,
    window_samples=256,
)
source = tm.CSVObservationSource(
    "measurements.csv",
    source_id="bridge-01:historical-test-2026-09",
    batch_size=128,
)

with tm.SessionRunner(source, session) as runner:
    for result in runner:
        for report in result.reports:
            print(report.to_dict())
```

The reader closes when the runner exits, including on an exception or early
loop exit. This is a deterministic file replay adapter, not a filesystem
watcher or a live-file tailer.
