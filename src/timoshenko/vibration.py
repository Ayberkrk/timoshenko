"""Single-degree-of-freedom and proportional vibration primitives."""

from __future__ import annotations

from dataclasses import dataclass
import math

from ._validation import positive as _positive


def natural_frequency_hz(mass_kg: float, stiffness_n_m: float) -> float:
    """Undamped natural frequency ``sqrt(k/m)/(2*pi)`` for an SDOF system."""
    m, k = _positive("mass_kg", mass_kg), _positive("stiffness_n_m", stiffness_n_m)
    return math.sqrt(k / m) / (2.0 * math.pi)


def damping_ratio(mass_kg: float, stiffness_n_m: float, damping_n_s_m: float) -> float:
    """Viscous damping ratio ``c/(2*sqrt(k*m))``."""
    m, k = _positive("mass_kg", mass_kg), _positive("stiffness_n_m", stiffness_n_m)
    c = float(damping_n_s_m)
    if not math.isfinite(c) or c < 0.0:
        raise ValueError("damping_n_s_m must be finite and non-negative")
    return c / (2.0 * math.sqrt(k * m))


@dataclass(frozen=True)
class HarmonicResponse:
    displacement_amplitude_m: float
    phase_lag_rad: float
    frequency_ratio: float


@dataclass(frozen=True)
class RayleighDampingResult:
    """Two-frequency fit for mass- and stiffness-proportional viscous damping."""

    frequency_1_hz: float
    damping_ratio_1: float
    frequency_2_hz: float
    damping_ratio_2: float
    alpha_mass_s_inv: float
    beta_stiffness_s: float

    def modal_damping_ratio(self, frequency_hz: float) -> float:
        """Evaluate the fitted Rayleigh damping ratio at a positive frequency."""
        frequency = _positive("frequency_hz", frequency_hz)
        omega = 2.0 * math.pi * frequency
        ratio = 0.5 * (self.alpha_mass_s_inv / omega + self.beta_stiffness_s * omega)
        if not math.isfinite(ratio):
            raise ValueError("Rayleigh damping ratio is non-finite at this frequency")
        return ratio

    def to_dict(self) -> dict[str, float | str]:
        return {
            "frequency_1_hz": self.frequency_1_hz,
            "damping_ratio_1": self.damping_ratio_1,
            "frequency_2_hz": self.frequency_2_hz,
            "damping_ratio_2": self.damping_ratio_2,
            "alpha_mass_s_inv": self.alpha_mass_s_inv,
            "beta_stiffness_s": self.beta_stiffness_s,
            "alpha_unit": "s^-1",
            "beta_unit": "s",
        }


def rayleigh_damping_coefficients(
    frequency_1_hz: float,
    damping_ratio_1: float,
    frequency_2_hz: float,
    damping_ratio_2: float,
) -> RayleighDampingResult:
    """Fit passive Rayleigh coefficients to two modal damping targets.

    For ``C = alpha_M M + beta_K K``, modal damping is
    ``zeta(omega) = alpha_M/(2 omega) + beta_K omega/2``. Frequencies are
    supplied in Hz and converted internally to angular frequency. Negative
    fitted coefficients are rejected because they do not define a passive
    two-term Rayleigh damping model over positive frequencies.
    """
    f1, f2 = _positive("frequency_1_hz", frequency_1_hz), _positive("frequency_2_hz", frequency_2_hz)
    z1, z2 = float(damping_ratio_1), float(damping_ratio_2)
    if not math.isfinite(z1) or z1 < 0.0 or not math.isfinite(z2) or z2 < 0.0:
        raise ValueError("target damping ratios must be finite and non-negative")
    original = (f1, z1, f2, z2)
    if f2 < f1:
        f1, f2, z1, z2 = f2, f1, z2, z1
    relative_gap = (f2 - f1) / f2
    if relative_gap <= 1e-8:
        raise ValueError("target frequencies must be distinct and sufficiently separated")
    omega_1, omega_2 = 2.0 * math.pi * f1, 2.0 * math.pi * f2
    if not math.isfinite(omega_1) or not math.isfinite(omega_2) or omega_1 <= 0.0 or omega_2 <= 0.0:
        raise ValueError("target frequencies are outside the supported numerical range")
    ratio = omega_1 / omega_2
    denominator = 1.0 - ratio * ratio
    alpha = 2.0 * omega_1 * (z1 - z2 * ratio) / denominator
    beta = 2.0 * (z2 - z1 * ratio) / (omega_2 * denominator)
    if not math.isfinite(alpha) or not math.isfinite(beta):
        raise ValueError("Rayleigh coefficient fit produced a non-finite value")
    alpha_tolerance = 1e-12 * max(omega_1 * z1, omega_2 * z2, math.ulp(0.0))
    beta_tolerance = 1e-12 * max(z1 / omega_1, z2 / omega_2, math.ulp(0.0))
    if alpha < -alpha_tolerance or beta < -beta_tolerance:
        raise ValueError("these two targets require a negative coefficient and cannot be fit by passive Rayleigh damping")
    alpha, beta = max(alpha, 0.0), max(beta, 0.0)
    result = RayleighDampingResult(
        frequency_1_hz=original[0],
        damping_ratio_1=original[1],
        frequency_2_hz=original[2],
        damping_ratio_2=original[3],
        alpha_mass_s_inv=alpha,
        beta_stiffness_s=beta,
    )
    if not (
        math.isclose(result.modal_damping_ratio(original[0]), original[1], rel_tol=1e-9, abs_tol=1e-12)
        and math.isclose(result.modal_damping_ratio(original[2]), original[3], rel_tol=1e-9, abs_tol=1e-12)
    ):
        raise ValueError("Rayleigh coefficient fit could not reproduce both targets at floating-point precision")
    return result


def harmonic_response(force_amplitude_n: float, excitation_hz: float, mass_kg: float,
                      stiffness_n_m: float, damping_n_s_m: float) -> HarmonicResponse:
    """Steady-state displacement amplitude and phase for a harmonically forced SDOF."""
    force = float(force_amplitude_n)
    if not math.isfinite(force):
        raise ValueError("force_amplitude_n must be finite")
    excitation = float(excitation_hz)
    if not math.isfinite(excitation) or excitation < 0.0:
        raise ValueError("excitation_hz must be finite and non-negative")
    m, k = _positive("mass_kg", mass_kg), _positive("stiffness_n_m", stiffness_n_m)
    zeta = damping_ratio(m, k, damping_n_s_m)
    omega_n = math.sqrt(k / m)
    ratio = (2.0 * math.pi * excitation) / omega_n
    denominator = math.hypot(1.0 - ratio**2, 2.0 * zeta * ratio)
    if denominator == 0.0:
        raise ValueError("undamped resonance has unbounded steady-state response")
    amplitude = abs(force) / k / denominator
    phase = math.atan2(2.0 * zeta * ratio, 1.0 - ratio**2)
    return HarmonicResponse(amplitude, phase, ratio)
