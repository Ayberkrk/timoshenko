# Persistent history stores

`HistoryStore` is the structural protocol consumed by `MonitoringSession`: implementations provide idempotent batch receipts, event-time observation queries, and project-run history. The package includes `SQLiteStore` for a local file and optional `PostgresStore` for a PostgreSQL service. Both persist the asset graph (`Asset`, `Relation`), point observations/batches, and JSON analysis results.

SQLite files use write-ahead logging (WAL), allowing independent connections to read while a writer is active. SQLite serializes writers; each connection waits up to its configured `timeout_seconds` before raising `sqlite3.OperationalError`. A connection remains thread-affine as required by Python's sqlite3 defaults; use one store connection per thread or process.

## Idempotent batch ingestion

Both backends implement the same batch contract. `append_batch` requires both `ObservationBatch.batch_id` and `source_id`. The unique source/batch pair is stored with a deterministic SHA-256 digest of ordered observation content:

- New pair: all rows and its batch receipt commit in one transaction.
- Same pair and same content: no rows are inserted; `was_duplicate=True` is returned.
- Same pair but changed content: a `ValueError` is raised and the transaction does not rewrite prior data.

`has_batch(batch)` answers the same question without writing: it returns whether this exact batch is stored and raises the same `ValueError` for changed content. `MonitoringSession` uses it to skip processed batches, then calls `append_batch` only after processing succeeds. PostgreSQL reads run in autocommit mode; each mutation uses an explicit transaction so a successful ingestion is visible to other connections before an acknowledging source commits its delivery.

Repeated identical observations *within* one batch are preserved by their record index. The store does not use value/time-based deduplication because two equal readings can be legitimate sensor samples.

## Event-time and arrival-time reads

`observations(..., order_by="event_time")` sorts finite timestamps ascending and places timestamp-free snapshots after them. `order_by="arrival"` uses persisted insert order. Optional start/end bounds apply to event timestamps; untimestamped records do not match a bounded query. Late values are retained and can appear before earlier-ingested readings in event-time order.

`recent_observations(sensor_id=..., unit=..., limit=...)` returns a bounded, good-quality, timestamped event-time tail for one sensor. It does not bridge time gaps or resample. `MonitoringSession.restore()` uses these tails to rebuild its current synchronized sample window after an application restart, regardless of which built-in store is configured.

`prune_before(event_timestamp)` explicitly deletes timestamped observation rows older than the cutoff and returns the deleted row count. Untimestamped observations, analysis runs, and batch receipts are retained. Keeping receipts means a replay of an expired batch remains idempotent and does not restore its deleted rows. Pruning is explicit; the store never deletes records automatically.

## PostgreSQL backend

Install `timoshenko-engine[postgres]` and construct `PostgresStore(dsn)` to use PostgreSQL through the same `HistoryStore` contract. The adapter creates its tables in a dedicated `timoshenko` schema by default; pass a simple `schema` name to isolate multiple applications in one database. It has no dependency on SQLite and stores JSON-compatible metadata and project results with the same semantics. Use one synchronous store instance per worker. PostgreSQL integration tests run in CI against a PostgreSQL service; SQLite users do not need the optional driver.

## Analysis history

`save_run(ProjectRunResult)` persists the serializable result with input hashes, method, project ID, and creation time. Pass a caller-chosen `run_id` when retries should use one stable run identity; duplicate IDs fail rather than overwrite. `get_run` and `list_runs` return decoded JSON-compatible dictionaries.

## Current limits

The store is synchronous and local. It does not provide encryption, replication, background ingestion, automatic retention, or a transaction spanning the database and an external source. Schema v1 databases migrate additively to v2, which adds event-time pruning and project-run query indexes without rewriting stored records. Keep the database on storage with appropriate backups and access controls for the deployment.
