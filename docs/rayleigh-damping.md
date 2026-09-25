# Rayleigh damping coefficient helper

Rayleigh, or proportional viscous, damping represents a damping matrix as
`C = alpha_M M + beta_K K`, combining mass and stiffness proportional terms.
This pattern appears in structural dynamics software, including the
[OpenSees Rayleigh command](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/damping/rayleigh.html).

For a classically damped mode with angular natural frequency `omega`, the
modal damping ratio is

```text
zeta(omega) = alpha_M / (2 omega) + beta_K omega / 2
```

`tm.rayleigh_damping_coefficients(...)` solves the two simultaneous equations
for two specified modal frequency/damping targets. Frequencies are accepted in
Hz and converted to rad/s. The returned `RayleighDampingResult` reports
`alpha_mass_s_inv` (s⁻¹), `beta_stiffness_s` (s), the supplied targets, and a
`modal_damping_ratio(frequency_hz)` evaluator for the fitted curve.

```python
import timoshenko as tm

fit = tm.rayleigh_damping_coefficients(
    frequency_1_hz=0.8,
    damping_ratio_1=0.02,
    frequency_2_hz=4.0,
    damping_ratio_2=0.02,
)
print(fit.alpha_mass_s_inv, fit.beta_stiffness_s)
print(fit.modal_damping_ratio(2.0))
```

The function rejects non-positive or near-identical target frequencies,
negative/non-finite target ratios, and targets that require a negative
coefficient. It fits two points only. Rayleigh damping changes with frequency,
so the two targets do not imply a constant damping ratio for other modes.

This helper returns coefficients only; a host solver determines which mass and
stiffness matrices those coefficients multiply. It does not build `C`, identify
material damping, or select initial/current/committed stiffness. Literature
shows material limits: damping ratios identified from recorded earthquake
responses of 24 instrumented buildings increased roughly linearly with modal
frequency and gave no support for a mass-proportional term
([Cruz & Miranda, 2017](https://doi.org/10.1016/j.engstruct.2017.02.001));
OpenSees also warns about use with nonlinear concentrated-plasticity time
history analysis. Alternatives have been proposed for matching damping ratios
over a broader frequency range ([2020 study](https://doi.org/10.1016/j.engstruct.2020.110178)).
Treat this result as one documented model option, not a universal damping
measurement or safety criterion.
