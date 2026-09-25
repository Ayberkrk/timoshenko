# Live monitoring sessions (0.8)

`MonitoringSession` accepts observations supplied by a host application and runs modal screening on a bounded rolling window. This is the engine-side session and window lifecycle; it does not open a network connection or start a background thread. A caller can use a sensor gateway, web service, or Cauren process to construct batches and feed them to `ingest()`.

```python
import timoshenko as tm

structure = tm.Structure(
    structure_id="bridge-01",
    story_masses_kg=[120_000.0],
    story_stiffness_n_m=[85_000_000.0],
)
session = tm.MonitoringSession(
    structure,
    sensor_ids=["deck-a", "deck-b"],
    units=["m/s^2", "m/s^2"],
    sampling_hz=100.0,
    window_samples=2048,
    hop_samples=512,
    analysis_options={"nperseg": 512, "max_modes": 4},
)

batch = tm.ObservationBatch(
    observations,  # timestamped, synchronized samples for the configured sensors
    source_id="gateway-01",
    batch_id="gateway-01:sequence-000123",
)
result = session.ingest(batch)
for report in result.reports:
    print(report.to_dict())
```

For a single sensor, the session calls `modal.identify` (peak picking). For two or more sensors, it calls Welch FDD and requires a common unit. `analysis_options` are validated against the selected method. Reports include event time, method, modal output, updated reference model, and evidence-oriented health comparison.

## Time and quality policy

- Timestamps are Unix seconds and must be within the configured tolerance of the explicit sample grid (`sampling_hz`). The default tolerance is one quarter of a sample interval.
- Every configured channel must have one good-quality value for a grid point. A missing, rejected, late, or invalid point breaks continuity; the session waits for a fresh full contiguous window and never interpolates.
- Samples not in the configured sensor set, bad-quality samples, missing timestamps, off-grid times, non-monotonic per-sensor times, and unit mismatches are excluded and counted in `SessionIngestResult`.
- Optional `SQLiteStore` persistence uses source and batch IDs for idempotency. A replayed identical batch is ignored by the session; a reused batch ID with changed contents raises through the store's integrity check.
- Maximum configuration is 32 channels and 65,536 samples per channel. FDD itself caps each FFT segment at 4,096 samples. Buffers retain only the rolling window plus bounded timestamp-completion bookkeeping.

## Limits

This session does not provide MQTT/OPC UA/HTTP clients, reconnection, background scheduling, alert thresholds, safety classifications, automatic clock synchronization, resampling, or persistence-based session restoration. The process host owns those policies. The returned health object is an evidence comparison, not a damage diagnosis or safety decision. See [numerical-methods.md](numerical-methods.md), [data-contract.md](data-contract.md), and [storage.md](storage.md).

Run the synthetic example from the repository root with:

```bash
PYTHONPATH=Timoshenko/src python Timoshenko/examples/live_session.py
```
