# Timoshenko architecture

Timoshenko is a small embeddable engineering engine. It provides shared numerical/data contracts and a local one-shot runner; it does not own a web server, broker, dashboard, database cluster, or project-specific decision rules.

```text
User code / Cauren / another host application
    ├── tm.<equation>(...)                 direct analytic calculation
    ├── tm.modal / tm.health / tm.update   composable analysis steps
    └── tm.load_project + tm.run_project   explicit local manifest workflow
                 │
       validated data contracts and provenance
                 │
   mechanics · sections · beams · vibration · modal/FDD
                 │
  optional adapters / storage / reports (future releases)
```

## Design decisions

- **Engine core:** explicit project inputs, common result objects, validation, provenance, and operation composition. `monitor` and `run_project` are deterministic one-shot entry points for the supplied batch.
- **Small dependency base:** NumPy is required by the current package; integrations with Cauren are optional at runtime. Database, broker, BIM, API, and chart libraries should be extras when there is a demonstrated need.
- **Composable APIs:** calculation functions are importable directly from `timoshenko` and grouped by topic (`sections`, `mechanics`, `beams`, `vibration`, `stability`, `oma`, `health`). A project runner composes those parts but users can call them independently.
- **Explicit lifecycle:** there is no hidden global runtime. Load a manifest, validate the model and sources, execute once, serialize the result, then close/release input resources. Streaming sessions and resumable state are future layers.
- **Host integration:** Cauren and other applications own their API, risk interpretation, UI, and business workflows. `cauren_physics.timoshenko_adapter` is an optional compatibility boundary; the engine itself has no Cauren dependency.
- **Result trust:** every method states its assumptions and known limits. A numerical result is not a design approval, diagnosis, or safety status.

## Planned boundaries

`SourceAdapter` should turn an external protocol into typed `Observation` records. A `Processor` transforms an immutable/bounded observation batch. A `StorageAdapter` persists raw input plus provenance and state changes. A `Reporter` serializes results or renders a view. These interfaces should be introduced when implemented by at least one real adapter; version 0.6 does not claim a plugin framework.

## Why not a full general FEM solver now?

FEM needs mesh/element/material/constraint contracts, sparse linear algebra, solver convergence and verification. It is a distinct deep subsystem. The current `Structure` is explicitly a lumped-mass shear-building reference model; the analytical primitives are useful even without a mesh. A future solver integration should use an adapter boundary instead of implying the existing model is general FEM.
