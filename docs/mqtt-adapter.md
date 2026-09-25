# MQTT observation adapter (1.2)

The built-in MQTT adapter is optional. From the repository root, install the source checkout with its MQTT extra:

```bash
python -m pip install './Timoshenko[mqtt]'
```

After publication, install it with `python -m pip install 'timoshenko-engine[mqtt]'`.

The Paho dependency is imported only when opening a source. The adapter uses Paho's callback API v2 and network loop, and resubscribes from the connect callback after a successful (re)connection. These choices follow the [Paho client lifecycle and callback API](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html) and its [callback migration notes](https://eclipse.dev/paho/files/paho.mqtt.python/html/migrations.html).

```python
import timoshenko as tm

registry = tm.PluginRegistry.load_entry_points()
source = registry.create_source(
    "mqtt",
    host="broker.example.net",
    port=8883,
    topic="bridge-01/sensors/batches",
    qos=1,
    client_id="timoshenko-bridge-01",
    username="collector",
    password="load-from-your-secret-store",
    tls=True,
)

with tm.SQLiteStore("bridge-history.sqlite") as store:
    session = tm.MonitoringSession(
        structure,
        sensor_ids=["deck-a", "deck-b"],
        units=["m/s^2", "m/s^2"],
        sampling_hz=100.0,
        window_samples=2048,
        store=store,
    )
    with tm.SessionRunner(source, session) as runner:
        for ingestion in runner:
            for report in ingestion.reports:
                tm.report.save_html(report, "reports/latest.html")
```

## Payload contract

Each publication on the subscribed concrete topic contains one UTF-8 JSON object, limited by `max_payload_bytes`:

```json
{
  "schema_version": 1,
  "source_id": "gateway-01",
  "batch_id": "gateway-01:sequence-000042",
  "observations": [
    {
      "sensor_id": "deck-a",
      "name": "acceleration",
      "unit": "m/s^2",
      "value": 0.012,
      "timestamp": 1800000000.01,
      "quality": true,
      "asset_id": "bridge-01",
      "metadata": {"axis": "vertical"}
    }
  ]
}
```

Every envelope needs `schema_version=1`, a stable source ID, a unique batch ID, and at least one event-timestamped observation. `Observation` validates finite values/timestamps and preserves the envelope's source ID. Publish synchronized channel observations together where possible; the session aligns them to the configured sample grid. MQTT message IDs are not used as batch IDs because they are transport-local and do not provide durable source identity. MQTT QoS and retained-message behavior are defined by the broker protocol; see the [OASIS MQTT 5.0 standard](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html).

## Delivery and failure behavior

- QoS 1 or 2 deliveries are manually acknowledged only after `SessionRunner` successfully calls `session.ingest()`. With `SQLiteStore`, the observation batch is committed before the acknowledgement. `clean_session=False` is the default and requires a stable client ID so the broker can retain session state across reconnects. Use unique IDs so a redelivery can be deduplicated.
- The adapter uses a bounded in-memory queue (`queue_capacity`, default 1024). An overflow or malformed/oversized payload stops the source with `MQTTSourceError`; it never silently counts the batch as valid. Configure capacity for expected rate/burst and monitor source failures.
- Retained publications are skipped by default because the latest retained sample is not necessarily a fresh sample. The count is available through `retained_drop_count`; `allow_retained=True` opts in.
- `tls=True` uses Paho's default TLS context. For custom certificate configuration or a custom Paho client, inject `client_factory`. Credentials should come from an application secret store.
- Paho handles network-loop reconnection; the adapter resubscribes on reconnect. Paho documents that its client session state is held in memory and is not restored after process restart, so this adapter does not claim process-restart delivery recovery. Broker persistence/QoS cannot replace input storage and application-level processing guarantees.
- Source errors propagate through `SessionRunner`; it does not hide transport or payload failures. Calling `close()` ends a blocked read.

The MQTT schema is a Timoshenko adapter contract, not an assertion that every MQTT deployment uses the same payload. The adapter does not make structural risk decisions. Validate timestamp origin, clock synchronization, units, sensor calibration, broker authentication and deployment reliability with the system owner.
