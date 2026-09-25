# Observation source adapters

Timoshenko separates analysis/session logic from the system that collects sensor data. Any gateway can implement `tm.ObservationSource` as a small synchronous pull interface:

```python
import timoshenko as tm

class GatewaySource:
    def open(self):
        self.client.connect()

    def read_batch(self):
        payload = self.client.read(timeout=1.0)
        if payload is None:
            return None  # end-of-stream for finite sources
        return tm.ObservationBatch(
            [tm.Observation(**item) for item in payload.items],
            source_id=payload.source_id,
            batch_id=payload.sequence_id,
        )

    def close(self):
        self.client.disconnect()

with tm.SessionRunner(GatewaySource(), session, max_batches=1000) as runner:
    for result in runner:
        for report in result.reports:
            consume(report)
```

`read_batch()` returns one arrival-order `ObservationBatch`; return `None` only when a finite source has ended. A live source should block up to its configured timeout or return a batch, depending on the gateway design. The source owns authentication, transport parsing, timeout selection, reconnect/backoff, and protocol quality mapping. The runner passes batches to `MonitoringSession.ingest()` and yields each `SessionIngestResult` unchanged.

`SessionRunner` is a context manager: it opens once and always attempts to close when the `with` block exits, including early loop breaks and exceptions. It does not retry or swallow source errors. `max_batches` is an optional deterministic bound useful for finite replays and controlled jobs. A source must be closed by exiting the `with` block; callers should not leave the context open indefinitely after stopping iteration.

This version provides the contract and lifecycle coordinator, not an MQTT/OPC UA/HTTP client. Concrete protocol adapters should be separately packaged and imported only by users who need them, so the NumPy-based core stays lightweight. They should map transport-specific fields into `Observation` without silently changing units, timestamps, quality, or provenance.
