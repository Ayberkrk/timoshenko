"""Single-degree-of-freedom linear vibration primitives."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and greater than zero")
    return value


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
