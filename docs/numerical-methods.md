# Numerical methods and calculation boundaries

This note records the equations exposed by the current package and the assumptions that bound their use. Public function arguments use SI units. Functions reject non-finite or non-positive physical parameters where those are invalid; signed forces, moments, stresses, and temperature changes preserve sign.

## 0.2 cross-sections and elementary mechanics

For a rectangle of width `b` and height `h`, the package reports `A = b h`, `I_y = b h^3/12`, `I_z = h b^3/12`, and the corresponding centroidal elastic section moduli. For a solid circle, `A = pi d^2/4` and `I = pi d^4/64`. The concentric circular tube uses outer-minus-inner area and inertia.

The elastic primitives are `sigma = N/A`, `sigma_b = M/S`, average shear `tau_avg = V/A`, solid-rectangle peak shear `tau_max = 3V/(2A)`, uniaxial strain `epsilon = sigma/E`, free thermal strain `epsilon_T = alpha delta_T`, and isotropic elasticity `E = 2G(1+nu)`. These are section-level relations; they do not combine stress components or judge material capacity.

## 0.2 closed-form beam cases

For a prismatic, linearly elastic beam under small deflection, the bending terms are:

| Support and loading | Bending deflection at reported location |
|---|---:|
| Cantilever, end point load `P`, free end | `P L^3 / (3 E I)` |
| Cantilever, full-span uniform load `w`, free end | `w L^4 / (8 E I)` |
| Simply supported, center point load `P`, midspan | `P L^3 / (48 E I)` |
| Simply supported, full-span uniform load `w`, midspan | `5 w L^4 / (384 E I)` |

If both `G` and `A` are provided, the result also includes the first-order shear contribution `Q L / (kappa G A)` using the corresponding shear resultant factor: `P L`, `w L^2/2`, `P L/4`, or `w L^2/8`. The default rectangular-section shear correction is `kappa=5/6`; users can provide a different coefficient appropriate to their section/theory. Bending and shear terms are returned separately and summed by `total_m`.

The shear split is an engineering approximation. Timoshenko beam theory adds transverse shear deformation to Euler–Bernoulli bending, but shear coefficients and deflection definitions need care; the functions do not claim general Timoshenko-beam finite-element or arbitrary-load solutions. See the primary beam solution discussions at [Cowper (1966)](https://doi.org/10.1061/JMCEA3.0001048), [Timoshenko-beam solutions (1995)](https://doi.org/10.1061/%28ASCE%290733-9399%281995%29121%3A6%28763%29), and the shear-coefficient formulation paper [Dorfmann and coworkers (2017)](https://doi.org/10.1061/%28ASCE%29EM.1943-7889.0001297).

## 0.2 single-degree-of-freedom vibration

For positive lumped mass `m`, stiffness `k`, and nonnegative viscous damping `c`, the package calculates `f_n = sqrt(k/m)/(2 pi)` and `zeta = c/(2 sqrt(k m))`. Harmonic response uses `r = omega/omega_n`, displacement amplitude `|F_0|/k / sqrt((1-r^2)^2+(2 zeta r)^2)`, and phase lag `atan2(2 zeta r, 1-r^2)`. It is a steady-state SDOF solution, not a transient integrator or a multi-degree-of-freedom modal solver.

## 0.3 torsion, elastic stability, plane stress, and pressure

For a solid or concentric hollow circular shaft, the polar area moment is `J = pi (D_o^4-D_i^4)/32`. Under uniform Saint-Venant torsion, the API reports outer-fiber stress `tau_max = T (D_o/2)/J` and twist `phi = T L/(G J)`. It does not accept non-circular sections, restrained warping, variable torque/section, or plastic torsion. Classical Saint-Venant torsion is reviewed in engineering mechanics literature; the circular-section assumptions are materially narrower than arbitrary-section torsion ([UBC mechanics note](https://civil-terje.sites.olt.ubc.ca/files/2023/08/Saint-Venant-Torsion.pdf), with later work on section torsion factors [arXiv:0912.2622](https://arxiv.org/abs/0912.2622)).

For a selected buckling axis, ideal Euler critical force is `P_cr = pi^2 E I/(K L)^2`; geometric slenderness is `K L/sqrt(I/A)`. `K` must be provided or deliberately defaulted to one (ideal pin-pin). Initial crookedness, residual stress, eccentric load, inelastic behavior, frame sway, interaction, and design-code resistance are not modeled. This is a bifurcation estimate for an ideal elastic column, not a column capacity check.

For plane stress `(sigma_x, sigma_y, tau_xy)`, the in-plane principal values are `(sigma_x+sigma_y)/2 +/- sqrt(((sigma_x-sigma_y)/2)^2+tau_xy^2)`. In-plane maximum shear is the square-root term; von Mises equivalent stress assumes zero out-of-plane normal/shear components and is `sqrt(sigma_x^2-sigma_x sigma_y+sigma_y^2+3 tau_xy^2)`. It is an equivalent stress only; no yield limit is applied. NASA structural-analysis reports document use of the von Mises criterion in isotropic plane-stress formulations ([NASA report](https://ntrs.nasa.gov/api/citations/19750015682/downloads/19750015682.pdf)).

For a closed-end thin cylindrical wall under net pressure `p`, membrane estimates are `sigma_hoop=p r/t` and `sigma_longitudinal=p r/(2t)`. The API reports `t/r` so the caller can judge the thin-wall approximation; it does not enforce a universal cutoff. Local discontinuities, heads/nozzles, thick-wall radial stress, external-pressure collapse, code factors, and fatigue are excluded. A 2021 experimental/analytical pressure-vessel study discusses these membrane assumptions and their stress measurements ([Materials Research, DOI: 10.1590/1980-5373-MR-2021-0495](https://doi.org/10.1590/1980-5373-MR-2021-0495)); a review of classical thin-wall versus other pressure-vessel formulas emphasizes their scope limits ([2015 review](https://www.sciencedirect.com/science/article/pii/S0308016115000071)).

## 0.1 signal analysis boundary

The 0.1 `modal.identify` implementation is a single-channel Hann-windowed FFT with local peak selection. It does not provide a stable automated operational modal analysis result for arbitrary field data. Method comparisons and reviews describe frequency-domain decomposition and automated frequency-domain methods that also assess mode shapes and stability/quality, including [Brincker, Zhang & Andersen (2001)](https://doi.org/10.1088/0964-1726/10/3/303) and a recent automated OMA study using MAC [(2024)](https://doi.org/10.1016/j.engstruct.2024.119210). Those are research directions for later releases, not capabilities implied by this peak picker.

## 0.4 multi-channel FDD

The `MultiChannelData` contract stores synchronized, regularly sampled rows with one common sample rate and channel metadata. `identify_fdd` removes each segment's mean, multiplies by a Hann window, estimates a one-sided Welch cross-spectral density matrix, and computes its Hermitian eigendecomposition at each frequency. The implementation searches local maxima in up to four leading singular-value curves; the matching eigenvector becomes the normalized complex mode-shape estimate. Secondary curves are screened against the maximum of the leading curve and candidate singular values are also compared locally with the leading value. `nperseg` sets resolution `fs/nperseg`; overlap changes the number of spectral averages. At least two segments are required. The initial API bounds one analysis to 32 channels and 4096 samples per FFT segment to keep temporary memory predictable.

FDD expects synchronized channels measuring the same physical quantity in the same units. Missing samples, asynchronous channels, unknown clock offsets, channel gain calibration, and resampling must be handled before constructing `MultiChannelData`. Unit labels are carried into the output but are not converted. A peak is a candidate mode, not automatically a structural mode: close/repeated modes, strong harmonics, low excitation, sensor nodes, nonstationarity, and operating/environmental variation need engineering review. This first FDD implementation does not estimate damping, use an SSI stabilization diagram, identify damage, or normalize temperature effects. See [FDD (Brincker et al., 2001)](https://doi.org/10.1088/0964-1726/10/3/303) and later automated FDD/MAC work [(2024)](https://doi.org/10.1016/j.engstruct.2024.119210).

## Interpretation and validation

Measured modal parameters vary with environmental and operational conditions. A frequency shift alone is not a damage diagnosis. The 2024 review of modal identification under environmental excitation summarizes method and interpretation issues ([DOI: 10.32604/sdhm.2024.053662](https://doi.org/10.32604/sdhm.2024.053662)); bridge SHM literature likewise documents environmental variability as a confounder. Timoshenko reports calculation inputs and outputs without asserting a project-specific safety conclusion.

This note documents equations, not code approval. Before safety-critical use, compare against a trusted engineering reference, verify units/sign conventions/boundary conditions, and obtain qualified engineering review.

## 1.6 scalar uncertainty propagation

`tm.uncertainty.propagate` accepts caller-supplied input estimates and either
independent standard uncertainties or a full covariance matrix. The
`first_order` method estimates local sensitivity coefficients by finite
differences and applies the GUM covariance law. The `monte_carlo` method
propagates a multivariate Gaussian input model using up to 100,000 draws. This
follows the general methods documented in [JCGM GUM 100 and its 2026
nonlinearity amendment](https://www.bipm.org/en/web/guest/publications/guides),
[JCGM 101](https://doi.org/10.59161/JCGM101-2008), and [NIST TN 1297 Appendix
A](https://www.nist.gov/pml/nist-technical-note-1297/nist-tn-1297-appendix-law-propagation-uncertainty).

The package propagates uncertainty; it does not estimate measurement errors,
calibration uncertainty, environmental variation, or model discrepancy. The
normal coverage interval from first-order propagation is an approximation, and
Monte Carlo is only as appropriate as the caller's Gaussian input model. The
full limits are in [uncertainty.md](uncertainty.md).
