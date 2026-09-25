# OGC SensorThings observation source

`SensorThingsObservationSource` reads one configured HTTP(S) SensorThings
Datastream `Observations` collection as JSON and emits one `ObservationBatch`
per server page. The implementation uses Python's standard library. Its
mapping is intentionally narrow; it is not a claim of full OGC conformance.

The OGC SensorThings Sensing v1.1 standard defines Observation JSON entities,
requires `phenomenonTime` and `result`, and uses server-driven `@iot.nextLink`
pagination. A client treats that next link as opaque and does not append query
options to it. This adapter follows those pagination rules and restricts links
to the configured service origin. See the [official OGC v1.1 specification](https://docs.ogc.org/is/18-088/18-088.html).

## Use

```python
import timoshenko as tm

source = tm.SensorThingsObservationSource(
    "https://sensors.example.org/v1.1/Datastreams(42)/Observations",
    sensor_id="bridge-01-accel-z",
    name="Deck vertical acceleration",
    unit="m/s^2",
    source_id="bridge-01:datastream-42",
    bearer_token="...",  # optional
    quality_parameter="measurement_valid",  # optional boolean in Observation.parameters
    default_quality=True,  # explicit opt-in if the service has no quality field
    timeout_s=10.0,
    max_response_bytes=2_000_000,
    max_observations_per_page=2048,
)
with tm.SessionRunner(source, session) as runner:
    for result in runner:
        consume(result)
```

The collection URL, stable sensor identity, and unit must be configured by the
caller. The adapter does not fetch Datastream metadata to infer the unit,
ObservedProperty, or sensor mapping. A missing `@iot.id` is allowed; it is
retained as metadata when present and participates in the stable page batch ID.

## Mapping and boundaries

| SensorThings field | Timoshenko field |
| --- | --- |
| `phenomenonTime` | Unix event timestamp; timezone-aware instant only |
| Scalar numeric `result` | `Observation.value` |
| Caller-supplied `sensor_id`, `name`, `unit` | Corresponding observation metadata |
| `@iot.id` | `metadata.sensorthings_observation_id`, when present |
| `@iot.nextLink` | Opaque pagination cursor; followed without query changes |
| Optional boolean in `parameters`, selected by caller | `Observation.quality` |

HTTP redirects are followed only within the configured origin (scheme, host
and port, with default ports normalized). A redirect elsewhere, including an
HTTPS to HTTP downgrade, raises `SensorThingsSourceError` before any request
is sent, because following it would forward the bearer token to that origin.

Each response has a byte limit and an observation-count limit. Only same-origin
pagination URLs are followed. Requests use JSON `Accept`, a finite timeout, and
an optional bearer authorization header. TLS certificate validation follows
Python's default HTTPS behavior.

This first reader accepts instant `phenomenonTime` and scalar finite numeric
`result` values. It rejects interval times, arrays/complex results, malformed
pages, and oversized responses. Quality is **false by default**, so unknown
quality cannot silently enter the monitoring window. Set
`quality_parameter="name"` to map a boolean in SensorThings `parameters`, or
explicitly set `default_quality=True` when the data owner confirms that all
records are valid. Other quality representations need an application-specific
mapping. It does not provide Datastream discovery, filtering/query generation,
metadata/unit conversion, polling, WebSub subscriptions, Tasking, DataArray,
MultiDatastream mapping, or a live alarm loop.

The built-in `sensorthings` source is discoverable through
`tm.PluginRegistry.load_entry_points()`; direct construction remains
available. Discovery is opt-in. The separate [WebSub extension](https://docs.ogc.org/is/24-032r1/24-032r1.html)
is a potential later path for asynchronous delivery, not implemented here.
