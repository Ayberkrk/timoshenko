# Data contracts

## Point observation

`Observation` is one finite numeric value with non-empty sensor name/ID/unit, optional Unix event time, a quality flag, optional asset/source IDs, and caller metadata. It records event time, not arrival time; a streaming adapter should retain ingestion time in metadata and never silently replace the device clock.

`ObservationBatch` preserves input/arrival order and may contain repeated, late, or out-of-order timestamps. It does not sort, deduplicate, interpolate, or infer a sample frequency. A consumer or storage adapter must choose and document those policies.

## Regular time series

`SensorData` represents one regularly sampled channel with one explicit sample rate. Optional timestamps are validated as strictly increasing but are not used to infer or repair an irregular clock. `MultiChannelData` is a rectangular `(sample, channel)` array: channels are aligned row by row and share one sample rate. Version 0.6 FDD requires one unit for all analyzed channels. Neither time-series class fabricates missing observations.

## Project input and result provenance

`ProjectManifest` version 1 is JSON and names one structure, one CSV, explicit channel headings/IDs/units, sampling frequency, analysis method, and options. Paths in the file are relative to the manifest. The runner hashes the manifest and input file, records the selected method/options, and returns modal results, model-update fields, and evidence comparison. It does not embed raw measurements in the result.

## Quality and missing values

- NaN/infinity and non-numeric CSV fields fail at load time.
- Missing CSV cells are rejected; no imputation is applied.
- Repeated/out-of-order point observations are retained in arrival order; policy belongs to later stream/history components.
- Unit labels are carried as strings. No automatic unit conversion is performed. FDD rejects mixed labels but cannot verify that two identical labels were calibrated to the same scale.
- Unknown measurement units should remain explicitly `unknown`; engineering interpretation then requires caller review.
