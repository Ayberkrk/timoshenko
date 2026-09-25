# Live monitoring sessions

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

If the session uses `SQLiteStore`, a process can explicitly restore its most recent synchronized contiguous samples before opening a source:

```python
with tm.SQLiteStore("history.sqlite") as store:
    session = tm.MonitoringSession(structure, ..., store=store)
    restored = session.restore()
    print(restored.to_dict())
    with tm.SessionRunner(source, session) as runner:
        for result in runner:
            ...
```

Restoration is bounded to the rolling-window size plus a small configurable history margin. The session discards bad-quality, wrong-unit, and off-grid rows, then keeps only the newest shared contiguous run. If that does not fill a window, it resumes with the partial contiguous tail and waits for new samples. Previously generated reports are not replayed, and the caller remains responsible for supplying the current model definition.

## Time and quality policy

- Timestamps are Unix seconds and must be within the configured tolerance of the explicit sample grid (`sampling_hz`). The default tolerance is one quarter of a sample interval.
- Every configured channel must have one good-quality value for a grid point. A missing, rejected, late, or invalid point breaks continuity; the session waits for a fresh full contiguous window and never interpolates.
- Samples not in the configured sensor set, bad-quality samples, missing timestamps, off-grid times, non-monotonic per-sensor times, and unit mismatches are excluded and counted in `SessionIngestResult`.
- Optional `SQLiteStore` persistence uses source and batch IDs for idempotency. A batch is persisted only after the session has processed it: if processing fails part-way, the batch is not stored, so a redelivery reaches the session and its remaining samples are accepted. A replayed batch that was already processed is ignored; a reused batch ID with changed contents raises through the store's integrity check.
- Option values in `analysis_options` are validated when the session is created, against the configured window length and sample rate, instead of when the first window completes.
- Every window updates the model passed to the constructor, so `update_scale_factor` is always relative to that original model. Pass `review_threshold_pct` to enable the health review flag; without it no flag is raised.
- Maximum configuration is 32 channels and 65,536 samples per channel. FDD itself caps each FFT segment at 4,096 samples. Buffers retain only the rolling window plus bounded timestamp-completion bookkeeping.

## Limits

This session does not provide MQTT/OPC UA/HTTP clients, reconnection, background scheduling, alert thresholds, safety classifications, automatic clock synchronization, or resampling. Restoration from a `SQLiteStore` is limited to observation buffers, as described above. The process host owns those policies. The returned health object is an evidence comparison, not a damage diagnosis or safety decision. See [numerical-methods.md](numerical-methods.md), [data-contract.md](data-contract.md), and [storage.md](storage.md).

Run the synthetic example from the repository root with:

```bash
PYTHONPATH=src python examples/live_session.py
```
