# Local SQLite history (0.7)

`SQLiteStore` uses the Python standard library and a local SQLite file. It persists a minimal asset graph (`Asset`, `Relation`), point observations/batches, and JSON analysis results. The database uses `PRAGMA user_version` schema migration marker 1 and foreign keys for asset relations.

## Idempotent batch ingestion

`append_batch` requires both `ObservationBatch.batch_id` and `source_id`. The unique source/batch pair is stored with a deterministic SHA-256 digest of ordered observation content:

- New pair: all rows and its batch receipt commit in one transaction.
- Same pair and same content: no rows are inserted; `duplicate_batch=True` is returned.
- Same pair but changed content: a `ValueError` is raised and the transaction does not rewrite prior data.

Repeated identical observations *within* one batch are preserved by their record index. The store does not use value/time-based deduplication because two equal readings can be legitimate sensor samples.

## Event-time and arrival-time reads

`observations(..., order_by="event_time")` sorts finite timestamps ascending and places timestamp-free snapshots after them. `order_by="arrival"` uses persisted insert order. Optional start/end bounds apply to event timestamps; untimestamped records do not match a bounded query. Late values are retained and can appear before earlier-ingested readings in event-time order.

## Analysis history

`save_run(ProjectRunResult)` persists the serializable result with input hashes, method, project ID, and creation time. Pass a caller-chosen `run_id` when retries should use one stable run identity; duplicate IDs fail rather than overwrite. `get_run` and `list_runs` return decoded JSON-compatible dictionaries.

## Current limits

The first store is synchronous and intended for a single process/thread. It has no automatic pruning, encryption, replication, migration beyond schema v1, lock/retry policy, background ingestion worker, or broker adapter. Keep the database on storage with appropriate backups and access controls for the deployment. The engine does not claim a transactional guarantee across the SQLite file and external sources.
