# Architecture

Timoshenko is a small embeddable engineering engine. It provides shared numerical and data contracts, analysis steps, and a bounded monitoring session. It does not own a web server, message broker, dashboard, database cluster, scheduler, or project-specific decision rules; the host application keeps those.

```text
Host application (your code, Cauren, a gateway service)
    │
    ├── tm.<equation>(...)                  analytic calculations, usable on their own
    ├── tm.modal / tm.update / tm.health    composable analysis steps
    ├── tm.monitor, tm.run_project          one-shot pipelines over supplied data
    └── tm.MonitoringSession                bounded rolling-window analysis of fed batches
                 │
       validated data contracts and provenance
       (SensorData, MultiChannelData, Observation, ObservationBatch)
                 │
   sections · mechanics · beams · vibration · modal / FDD · uncertainty
                 │
   source adapters (CSV, MQTT, SensorThings) · SQLite history · HTML reports
```

## Design decisions

- **Small core, explicit inputs.** NumPy is the only required dependency. Optional integrations are extras (`mqtt`) or plugins discovered through the `timoshenko.plugins` entry-point group. Nothing is inferred that the caller did not state: sample rates, units, and channel identities are always explicit.
- **Composable APIs.** Calculation functions are importable directly from `timoshenko` and grouped by topic modules (`sections`, `mechanics`, `beams`, `vibration`, `stability`, `modal`, `oma`, `health`). Pipelines such as `monitor`, `run_project`, and `MonitoringSession` only compose those parts.
- **Explicit lifecycle.** There is no hidden global runtime or background thread. `ObservationSource` implementations are opened, read, and closed by `SessionRunner`; a `MonitoringSession` analyzes only what the host feeds it and can restore its buffers from a `SQLiteStore` after a restart.
- **Host integration.** Applications own their API, user interface, alarm and risk policy, and engineering interpretation. For example, Cauren uses Timoshenko through an optional adapter and keeps its own risk thresholds; the engine has no dependency on any host.
- **Result trust.** Every method documents its assumptions and limits, and results carry the evidence behind them. A numerical result is not a design approval, damage diagnosis, or safety status.

## Extension points

Source adapters implement the `ObservationSource` protocol (`open`, `read_batch`, `close`, and optionally `acknowledge`). Built-in sources cover CSV replay, MQTT, and OGC SensorThings. The [plugin contract](plugin-contract.md) lets installed packages register additional source factories. Plugin families for processors, storage backends, and reporters are intentionally not defined until a real implementation needs them.

## Why not a general FEM solver?

FEM needs mesh, element, material, and constraint contracts, sparse linear algebra, solver convergence, and verification. It is a distinct deep subsystem. `Structure` is explicitly a lumped-mass shear-building reference model, and the analytic primitives are useful without a mesh. A future solver integration should sit behind an adapter boundary rather than implying that the existing model is general FEM.
