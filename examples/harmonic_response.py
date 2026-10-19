"""Steady-state harmonic response of a damped single-degree-of-freedom system."""

import math

import timoshenko as tm


def main() -> None:
    force_amplitude_n = 50_000.0
    mass_kg = 500.0
    stiffness_n_m = 200_000.0
    damping_n_s_m = 1_000.0  # 2 * 0.05 * sqrt(k m), a 5% damping ratio

    natural_hz = tm.natural_frequency_hz(mass_kg, stiffness_n_m)
    zeta = tm.damping_ratio(mass_kg, stiffness_n_m, damping_n_s_m)
    static_deflection_m = force_amplitude_n / stiffness_n_m

    print(f"Natural frequency: {natural_hz:.4f} Hz")
    print(f"Damping ratio: {zeta:.4f}")
    print(f"Static deflection F/k: {static_deflection_m * 1e3:.3f} mm")

    def amplification(ratio: float) -> float:
        response = tm.harmonic_response(
            force_amplitude_n=force_amplitude_n,
            excitation_hz=ratio * natural_hz,
            mass_kg=mass_kg,
            stiffness_n_m=stiffness_n_m,
            damping_n_s_m=damping_n_s_m,
        )
        return response.displacement_amplitude_m / static_deflection_m

    def phase_lag_degrees(ratio: float) -> float:
        response = tm.harmonic_response(
            force_amplitude_n=force_amplitude_n,
            excitation_hz=ratio * natural_hz,
            mass_kg=mass_kg,
            stiffness_n_m=stiffness_n_m,
            damping_n_s_m=damping_n_s_m,
        )
        return math.degrees(response.phase_lag_rad)

    # Dynamic amplification and phase lag between rest and twice resonance.
    print(f"{'ratio':>6} {'amplification':>14} {'phase lag (deg)':>16}")
    for index in range(21):
        ratio = index * 0.1
        print(f"{ratio:6.2f} {amplification(ratio):14.3f} {phase_lag_degrees(ratio):16.1f}")

    # A dense sweep pins the peak next to the closed-form resonance value
    # 1 / (2 zeta sqrt(1 - zeta^2)), reached at r = sqrt(1 - 2 zeta^2).
    peak_ratio = math.sqrt(1.0 - 2.0 * zeta**2)
    sweep_peak = max(amplification(index / 1_000.0) for index in range(0, 3_001))
    closed_form = 1.0 / (2.0 * zeta * math.sqrt(1.0 - zeta**2))
    print(f"Closed-form peak ratio: {peak_ratio:.4f}")
    print(f"Closed-form amplification: {closed_form:.4f}")
    print(f"Sweep peak amplification: {sweep_peak:.4f}")
    assert math.isclose(sweep_peak, closed_form, rel_tol=1e-3), (sweep_peak, closed_form)


if __name__ == "__main__":
    main()
