# Project manifest, version 1

A project manifest is an explicit JSON file for repeatable local analysis. “Automatic loading” means the manifest names the model, input file, channel headings, units, sample rate, analysis method, and options. Timoshenko does not infer absent engineering facts.

## Schema example

```json
{
  "schema_version": "1.0",
  "project": { "id": "bridge-demo", "name": "Bridge vibration example" },
  "structure": {
    "type": "shear_building",
    "id": "span-model",
    "story_masses_kg": [5000.0],
    "story_stiffness_n_m": [4934802.2]
  },
  "observations": {
    "file": "accelerations.csv",
    "sampling_hz": 100.0,
    "channels": [
      { "column": "deck_accel", "id": "deck-midspan-z", "unit": "m/s^2" }
    ]
  },
  "analysis": {
    "method": "peak_picking",
    "options": { "max_modes": 3, "min_peak_ratio": 0.15 }
  }
}
```

Paths are resolved relative to the manifest file. Manifest version 1 supports JSON manifests, CSV source data, and the shear-building model. A one-channel project uses `peak_picking`; a multi-channel aligned source uses `fdd` and all channels must have the same measurement unit. Sampling rate must be provided. Blank/non-numeric samples, unknown columns, duplicate channel identifiers, and unsupported schema versions fail with explicit errors; the loader does not impute or resample.

Allowed `peak_picking` options are `max_modes`, `min_frequency_hz`, `max_frequency_hz`, and `min_peak_ratio`. FDD additionally supports `nperseg`, `overlap`, `max_singular_values`, and `min_singular_value_ratio`. Unknown options are rejected.

## Run it

```python
import timoshenko as tm

project = tm.load_project("project/manifest.json")
result = tm.run_project(project)
print(result.to_dict())

# One-step convenience: the manifest is loaded and analyzed in this call.
result = tm.run_project("project/manifest.json")
```

The output carries project/model IDs, analysis method/options, absolute resolved source paths, SHA-256 hashes of both the manifest and CSV input, modal results, updated model parameters when modes are available, and evidence-oriented health comparison. No raw sensor data is embedded in the output. Hashes/provenance make it easier for the caller to detect changed inputs; they do not guarantee scientific repeatability across changed software or numerical libraries.

For a one-channel run, the documented uniform-stiffness update is applied. For multi-channel FDD, the same frequency-derived global scale is applied when peaks are available. In either case, observed modes are paired with reference modes by nearest frequency (`tm.modal.pair_modes`); the engine does not claim damage localization, independent story updates, automated mode tracking, or a safety decision.

## Generate the bundled synthetic example

From the repository root, run:

```bash
PYTHONPATH=src python3 examples/project_manifest.py
```

The script writes temporary CSV/JSON inputs, runs the manifest, prints a compact human-readable summary plus the structured report, and removes the temporary files when it exits.
