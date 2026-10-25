# Advanced operational modal analysis and channel alignment

The basic FDD estimate remains available as `tm.identify_fdd`. The
`tm.identify_ssi` routine adds covariance-driven stochastic subspace
identification (SSI-COV) for synchronized multi-channel output-only records.
It fits a caller-selected sequence of even state-space orders and reports
frequency, damping, complex mode shape, and the number of adjacent orders over
which a pole remained stable. Pole stability is a screening indicator; it does
not prove that the pole is a structural mode. Use a stabilization diagram and
engineering review for important decisions.

```python
result = tm.identify_ssi(
    aligned_data,
    block_rows=24,
    model_orders=(6, 12, 18, 24, 30),
    min_frequency_hz=0.5,
    max_frequency_hz=20.0,
    min_stable_orders=3,
)
for mode in result.modes:
    print(mode.frequency_hz, mode.damping_ratio, mode.stability_score)
```

SSI-COV estimates a covariance sequence, forms its block Toeplitz matrix,
extracts state-space realizations by SVD, and converts discrete poles to
continuous modal parameters. The record should be stationary, sufficiently
long, and sampled uniformly. The order set, block rows, and stability
tolerances affect the result. Close/repeated modes, poor excitation, short
records, and nonstationary operating conditions can produce missed or
spurious stable poles. To bound temporary memory, `block_rows * channel_count`
cannot exceed 1024. No automatic environmental correction is applied.

## EFDD damping estimate

`identify_fdd(..., estimate_damping=True)` selects the singular-value bell
whose mode vectors remain correlated with the peak vector, transforms that
bell to a correlation sequence, and fits the decay of its peaks. An
`FDDMode.damping_ratio` is `None` when the selected bell or decay is not
resolved. This estimate is optional because FDD peak identification does not
always provide enough bandwidth for damping estimation.

```python
fdd = tm.identify_fdd(aligned_data, nperseg=2048, estimate_damping=True)
for mode in fdd.modes:
    print(mode.frequency_hz, mode.damping_ratio, mode.damping_method)
```

For a multi-channel `MonitoringSession`, the same option can be set in
`analysis_options` alongside `nperseg` and `max_modes`.

Treat this as an operational screening estimate. Its value depends on
frequency resolution, segment averaging, modal overlap, excitation, and the
selected modal bell. Compare it with longer records or a separately validated
method when damping materially affects a decision.

## Aligning asynchronous channels

`TimedChannel` carries one channel's samples and event timestamps. Pass
explicit clock offsets and calibration coefficients to
`align_multichannel`; the function returns one or more contiguous
`AlignedSegment` objects, each containing a `MultiChannelData` array and its
shared timestamp grid.

```python
aligned = tm.align_multichannel(
    channels,
    sampling_hz=50.0,
    time_offsets_s={"deck-right": 0.012},
    calibration_scales={"deck-right": 1.02},
    calibration_offsets={"deck-right": -0.004},
    max_gap_s=0.05,
)
for segment in aligned.segments:
    fdd = tm.identify_fdd(segment.data)
```

The calibration formula is `scale * raw_value + offset`. All channels must
declare the same unit after the supplied conversion; the function does not
infer a dimensional conversion, sensor gain, clock offset, or clock drift.
The target sample rate cannot exceed the slowest channel's median rate. A
finite Kaiser-windowed sinc reconstruction applies a low-pass cutoff at the
target Nyquist frequency before resampling. Its finite support can cause edge
transients, and strongly irregular sampling only approximates ideal
band-limited reconstruction. Set `max_gap_s` to a value appropriate to the
source; grid points whose interpolation stencil crosses a larger gap are
dropped. Gaps are returned as segment boundaries, never interpolated across.
Segments shorter than eight samples are discarded.

## API and test status

The additions are `tm.SSIMode`, `tm.SSIResult`, `tm.identify_ssi`,
`tm.TimedChannel`, `tm.AlignedSegment`, `tm.AlignmentResult`, and
`tm.align_multichannel`. The existing `identify_fdd` API gains the optional
`estimate_damping` flag, while `FDDMode` gains nullable damping fields. The
test suite includes noisy stochastic modes, shape MAC, modal damping, channel
offset and calibration, downsampling, large gaps, and invalid time grids.
