# Scalar equation uncertainty propagation

Timoshenko wraps an existing scalar equation instead of requiring users to
rewrite it to get a first uncertainty estimate. The methods follow the GUM
law of propagation with sensitivity coefficients and input covariance, and
offer Monte Carlo propagation for nonlinear response to explicitly modeled
input distributions. The metrology foundations are JCGM [GUM 100 and its
2026 nonlinearity amendment](https://www.bipm.org/en/web/guest/publications/guides),
the [JCGM 101 Monte Carlo supplement](https://doi.org/10.59161/JCGM101-2008),
and [NIST TN 1297 Appendix A](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty).

## First-order propagation

For a scalar model `y = f(x)`, first-order propagation computes numerical
sensitivity coefficients `c_i = df/dx_i` and combines uncertainty as
`u_c(y)^2 = c.T @ covariance @ c`. This is a local linearization. If only
independent standard uncertainties are supplied, Timoshenko constructs a
diagonal covariance matrix. Correlated inputs require a full covariance matrix
in the same order as the `inputs` mapping.

```python
import timoshenko as tm

estimate = tm.uncertainty.propagate(
    tm.natural_frequency_hz,
    {"mass_kg": 120_000.0, "stiffness_n_m": 85_000_000.0},
    standard_uncertainties={"mass_kg": 600.0, "stiffness_n_m": 4_250_000.0},
    confidence_level=0.95,
)
print(estimate.to_dict())
```

`tm.propagate_uncertainty` is a top-level alias. Inputs are passed as keyword
arguments to any compatible user function or equation in the package. A
`UncertaintyResult` includes the nominal output, combined standard
uncertainty, normal coverage interval, method, and first-order sensitivity
coefficients.

## Monte Carlo propagation

```python
estimate = tm.uncertainty.propagate(
    tm.natural_frequency_hz,
    {"mass_kg": 120_000.0, "stiffness_n_m": 85_000_000.0},
    standard_uncertainties={"mass_kg": 600.0, "stiffness_n_m": 4_250_000.0},
    method="monte_carlo",
    samples=20_000,
    seed=42,
)
```

Monte Carlo samples a multivariate normal distribution with the supplied input
means and covariance. It reports the sample mean, sample standard deviation,
and empirical central coverage interval. The seed defaults to `0` for a
repeatable result. The sample count is limited to 100–100,000 and uncertain
input count to 32 to bound memory and runtime. It stops with an explicit error
if any sample falls outside the wrapped equation's domain; it does not discard
invalid samples.

## Interpretation limits

- The caller provides the nominal inputs, input uncertainty, covariance, units,
  and distribution assumptions. Timoshenko does not estimate them from sensor
  data or a calibration record.
- The independent-uncertainty shortcut assumes zero covariance. Correlation
  must be represented in a full positive-semidefinite covariance matrix.
- First-order propagation may be inaccurate for nonlinear equations or
  strongly non-normal output. Prefer Monte Carlo only when a multivariate
  Gaussian input model is defensible; this version does not sample arbitrary,
  bounded, or truncated distributions.
- The returned interval is not a design tolerance, failure probability,
  reliability index, code-compliance result, or safety decision. This API is
  scalar and does not yet propagate uncertainty through full modal/health
  reports.
