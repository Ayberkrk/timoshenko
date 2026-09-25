# Adapter and plugin contract (design draft)

**Status:** design only. Version 0.6 does not include plugin discovery or a runtime plugin manager. Introduce these interfaces only with a concrete adapter and compatibility policy.

## Boundaries

- `SourceAdapter` converts an external source into typed `Observation` records. It exposes source identity/version, validates configuration, preserves event/arrival times, and closes external resources deterministically.
- `Processor` consumes an explicit `ObservationBatch` and configuration and returns a typed result/findings. It must not mutate shared input arrays or hide model assumptions.
- `StorageAdapter` persists raw inputs, provenance, derived results, and checkpoints. Idempotency keys and transaction boundaries belong here; a future API must specify how replay and late data behave.
- `Reporter` maps result objects to JSON, tabular, or visual outputs without changing engineering calculations or risk meaning.

## Compatibility requirements

1. Core results and plugin configuration have independent schema/API versions.
2. A plugin declares supported core versions and fails clearly on an incompatible contract.
3. Optional protocol/BIM/API libraries are installed only by users who enable that adapter; the core remains usable without them.
4. Plugin errors retain source identity and processing stage; invalid measurements are not silently dropped.
5. Replays preserve original event time and input provenance. A processor should be deterministic for equal configuration, package versions, and input when its method permits determinism.
6. No plugin may set Cauren-specific risk thresholds in the generic engine.

## Future registration options

If third-party discovery becomes useful, prefer Python package entry points under a Timoshenko-owned group name and validate metadata before loading executable code. Initial built-in adapters should be explicitly constructed by the host; automatic import of every installed plugin is not part of the current runtime design.
