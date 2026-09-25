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

The shear split is an engineering approximation. Timoshenko beam theory adds transverse shear deformation to Euler-Bernoulli bending, but shear coefficients and deflection definitions need care; the functions do not claim general Timoshenko-beam finite-element or arbitrary-load solutions. See the primary beam solution discussions at [Cowper (1968)](https://doi.org/10.1061/JMCEA3.0001048), [Timoshenko-beam solutions (1995)](https://doi.org/10.1061/%28ASCE%290733-9399%281995%29121%3A6%28763%29), and the shear-coefficient formulation paper [Faghidian (2017)](https://doi.org/10.1061/%28ASCE%29EM.1943-7889.0001297).

## 0.2 single-degree-of-freedom vibration

For positive lumped mass `m`, stiffness `k`, and nonnegative viscous damping `c`, the package calculates `f_n = sqrt(k/m)/(2 pi)` and `zeta = c/(2 sqrt(k m))`. Harmonic response uses `r = omega/omega_n`, displacement amplitude `|F_0|/k / sqrt((1-r^2)^2+(2 zeta r)^2)`, and phase lag `atan2(2 zeta r, 1-r^2)`. It is a steady-state SDOF solution, not a transient integrator or a multi-degree-of-freedom modal solver.

## 0.3 torsion, elastic stability, plane stress, and pressure

For a solid or concentric hollow circular shaft, the polar area moment is `J = pi (D_o^4-D_i^4)/32`. Under uniform Saint-Venant torsion, the API reports outer-fiber stress `tau_max = T (D_o/2)/J` and twist `phi = T L/(G J)`. It does not accept non-circular sections, restrained warping, variable torque/section, or plastic torsion. Classical Saint-Venant torsion is reviewed in engineering mechanics literature; the circular-section assumptions are materially narrower than arbitrary-section torsion ([UBC mechanics note](https://civil-terje.sites.olt.ubc.ca/files/2023/08/Saint-Venant-Torsion.pdf), with later work on section torsion factors [arXiv:0912.2622](https://arxiv.org/abs/0912.2622)).

For a selected buckling axis, ideal Euler critical force is `P_cr = pi^2 E I/(K L)^2`; geometric slenderness is `K L/sqrt(I/A)`. `K` must be provided or deliberately defaulted to one (ideal pin-pin). Initial crookedness, residual stress, eccentric load, inelastic behavior, frame sway, interaction, and design-code resistance are not modeled. This is a bifurcation estimate for an ideal elastic column, not a column capacity check.

For plane stress `(sigma_x, sigma_y, tau_xy)`, the in-plane principal values are `(sigma_x+sigma_y)/2 +/- sqrt(((sigma_x-sigma_y)/2)^2+tau_xy^2)`. In-plane maximum shear is the square-root term; von Mises equivalent stress assumes zero out-of-plane normal/shear components and is `sqrt(sigma_x^2-sigma_x sigma_y+sigma_y^2+3 tau_xy^2)`. It is an equivalent stress only; no yield limit is applied. The equivalent stress follows von Mises (1913), *Mechanik der festen Körper im plastisch-deformablen Zustand*, Nachrichten der Gesellschaft der Wissenschaften zu Göttingen, Mathematisch-Physikalische Klasse, 582-592.

For a closed-end thin cylindrical wall under net pressure `p`, membrane estimates are `sigma_hoop=p r/t` and `sigma_longitudinal=p r/(2t)`. The API reports `t/r` so the caller can judge the thin-wall approximation; it does not enforce a universal cutoff. Local discontinuities, heads/nozzles, thick-wall radial stress, external-pressure collapse, code factors, and fatigue are excluded. A 2022 ultrasonic measurement study of thin-walled pressure vessels discusses these membrane assumptions and their stress measurements ([Materials Research, DOI: 10.1590/1980-5373-MR-2021-0495](https://doi.org/10.1590/1980-5373-MR-2021-0495)); a review of simple elastic hoop-stress formulas emphasizes their scope limits ([Sinclair & Helms, 2015, International Journal of Pressure Vessels and Piping](https://doi.org/10.1016/j.ijpvp.2015.01.006)).

## 0.1 signal analysis boundary

The 0.1 `modal.identify` implementation is a single-channel Hann-windowed FFT with local peak selection. It does not provide a stable automated operational modal analysis result for arbitrary field data. Method comparisons and reviews describe frequency-domain decomposition and automated frequency-domain methods that also assess mode shapes and stability/quality, including [Brincker, Zhang & Andersen (2001)](https://doi.org/10.1088/0964-1726/10/3/303) and a recent automated OMA study using MAC [(Cardoni et al., 2025)](https://doi.org/10.1016/j.engstruct.2024.119210). Those are research directions for later releases, not capabilities implied by this peak picker.

Damping is estimated separately from the frequency. A single periodogram of ambient response fluctuates by about 100% per bin, so half-power points taken from it land on noise spikes, and a Hann window alone has a half-power width of about 1.44 bins, so a narrow peak reports the window rather than the structure. `identify` therefore takes the half-power bandwidth from a Welch spectrum (Hann, 50% overlap) using the longest power-of-two segment that still gives eight averages, and returns `None` when that bandwidth is narrower than four bins. On a white-noise driven oscillator with 2% damping, 600 s records give estimates within about a factor of two; the value is a screening estimate, not a substitute for SSI or EFDD damping identification.

`update` and `health.assess` pair each observed frequency with the nearest reference mode on a logarithmic scale, keeping only the closest observed peak per reference mode (`tm.modal.pair_modes`). A uniform stiffness change scales all frequencies by the same factor, so pairing holds unless the change exceeds the spacing between modes. A change no larger than the spectral resolution is marked `resolution_limited`, and `review_recommended` requires an explicit `review_threshold_pct`.

## 0.4 multi-channel FDD

The `MultiChannelData` contract stores synchronized, regularly sampled rows with one common sample rate and channel metadata. `identify_fdd` removes each segment's mean, multiplies by a Hann window, estimates a one-sided Welch cross-spectral density matrix, and computes its Hermitian eigendecomposition at each frequency. The implementation searches local maxima in up to four leading singular-value curves; the matching eigenvector becomes the normalized complex mode-shape estimate. Secondary curves are screened against the maximum of the leading curve and candidate singular values are also compared locally with the leading value. `nperseg` sets resolution `fs/nperseg`; overlap changes the number of spectral averages. At least two segments are required. The initial API bounds one analysis to 32 channels and 4096 samples per FFT segment to keep temporary memory predictable.

FDD expects synchronized channels measuring the same physical quantity in the same units. Missing samples, asynchronous channels, unknown clock offsets, channel gain calibration, and resampling must be handled before constructing `MultiChannelData`. Unit labels are carried into the output but are not converted. A peak is a candidate mode, not automatically a structural mode: close/repeated modes, strong harmonics, low excitation, sensor nodes, nonstationarity, and operating/environmental variation need engineering review. This first FDD implementation does not estimate damping, use an SSI stabilization diagram, identify damage, or normalize temperature effects. See [FDD (Brincker et al., 2001)](https://doi.org/10.1088/0964-1726/10/3/303) and later automated FDD/MAC work [(Cardoni et al., 2025)](https://doi.org/10.1016/j.engstruct.2024.119210).

## Interpretation and validation

Measured modal parameters vary with environmental and operational conditions. A frequency shift alone is not a damage diagnosis. The review of modal identification under environmental excitation by Zhang et al. (2025) summarizes method and interpretation issues ([DOI: 10.32604/sdhm.2024.053662](https://doi.org/10.32604/sdhm.2024.053662)); bridge SHM literature likewise documents environmental variability as a confounder. Timoshenko reports calculation inputs and outputs without asserting a project-specific safety conclusion.

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

## 1.7 Rayleigh damping

For a classical proportional damping matrix `C = alpha_M M + beta_K K`, a
modal frequency `omega` has damping ratio
`zeta = alpha_M/(2 omega) + beta_K omega/2`. The 1.7 helper fits two target
frequency/damping pairs and evaluates the resulting curve; the host solver
still owns the mass/stiffness matrices and damping-model choice. See
[rayleigh-damping.md](rayleigh-damping.md), the [OpenSees command
definition](https://opensees.github.io/OpenSeesDocumentation/user/manual/model/damping/rayleigh.html),
and Cruz and Miranda's recorded-building evaluation
([2017](https://doi.org/10.1016/j.engstruct.2017.02.001)), which found damping
increasing roughly linearly with frequency. These sources show why a
two-target fit must not be interpreted as constant damping or assumed valid
for nonlinear response.

## 1.8 idealized I-section and rectangular tube

The `tm.i_section` and `tm.rectangular_tube_section` helpers compose sharp-
corner rectangles and use the parallel-axis theorem about the symmetry
centroid. They return area, centroidal second moments about both principal
axes, and elastic section moduli. Dimensions are metres. For a named rolled or
manufactured shape, use published catalog properties instead of this ideal
geometry; see [section-properties.md](section-properties.md) and the [AISC
Shapes Database](https://www.aisc.org/aisc/publications/steel-construction-manual/aisc-shapes-database-v160/).

These geometric equations do not calculate torsion constants, effective
widths, shear areas, local buckling, resistance, or code checks. Sharp corners
and uniform ideal walls omit fillets, weld details and manufacturing
tolerances.

## 1.9 polygon section geometry

`tm.polygon_section` evaluates signed boundary integrals for area, first
moments, both centroidal second moments and the product moment. Optional hole
rings are sign-normalized and subtracted; directional section moduli use the
outer boundary's extreme fibres. The formulas and validation rules are
specified in [polygon-sections.md](polygon-sections.md), based on Green's
theorem / shoelace polygon sums ([Bourke, 1988](https://paulbourke.net/geometry/polygonmesh/)).

Only simple, uniform-material planar polygons with non-overlapping holes are
supported. The result preserves `Ixy`; it does not transform to principal axes
or calculate stress for coupled bending. It also omits material interfaces,
plasticity, shear/torsion properties and design checks.
