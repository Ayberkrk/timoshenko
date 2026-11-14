"""Synthetic base excitation of a linear-elastic, fixed-base two-storey portal.

SI units; lumped floor masses and massless members. This is a numerical
example, not a measured earthquake or a structural safety assessment.
"""

from dataclasses import replace

import numpy as np

import timoshenko as tm


def main() -> None:
    material = tm.FrameMaterial(youngs_modulus_pa=200e9, shear_modulus_pa=200e9 / 2.6)
    section = tm.FrameSection(area_m2=0.02, second_moment_local_z_m4=8e-5)
    model = tm.StructuralModel(
        nodes=tuple(tm.FrameNode(x, y) for y in (0.0, 3.0, 6.0) for x in (0.0, 4.0)),
        members=tuple(
            tm.FrameMember(i, j, material, section)
            for i, j in ((0, 2), (1, 3), (2, 4), (3, 5), (2, 3), (4, 5))
        ),
        restraints=((True, True, True),) * 2 + ((False, False, False),) * 4,
        nodal_lumped_masses_kg=(0.0, 0.0, 1000.0, 1000.0, 1000.0, 1000.0),
    )
    frequencies = tm.analyze_modes(model, mode_count=2).frequencies_hz
    damping = tm.rayleigh_damping_coefficients(frequencies[0], 0.05, frequencies[1], 0.05)
    options = {
        "direction": "x",
        "rayleigh_mass_per_s": damping.alpha_mass_s_inv,
        "rayleigh_stiffness_s": damping.beta_stiffness_s,
    }
    # A smooth, finite four-second pulse, followed by four seconds of ring-down.
    times = np.linspace(0.0, 8.0, 4001)
    envelope = np.sin(np.pi * np.minimum(times, 4.0) / 4.0) ** 2
    ground = 0.5 * np.sin(2 * np.pi * frequencies[0] * times) * envelope
    response = tm.analyze_time_history(model, times, base_acceleration_m_s2=ground, **options)
    roof = np.asarray(response.displacements)[:, 4:6, 0]
    # Sum reactions at BOTH fixed supports before taking the absolute peak.
    base_shear = np.asarray(response.reactions)[:, :2, 0].sum(axis=1)
    print("First two natural frequencies (Hz):", frequencies)
    print("Target modal damping ratios: 0.05, 0.05")
    print(f"Peak relative roof displacement: {np.max(np.abs(roof)) * 1000:.3f} mm")
    print(f"Peak horizontal base shear (support reaction): {np.max(np.abs(base_shear)):.3f} N")

    # Quasi-static check: slowly ramp to a_g = 0.1 m/s^2 over 20 first-mode periods.
    # With massless members, -M*r*a_g is exactly the nodal load (-m*a_g, 0, 0).
    slow_times = np.linspace(0.0, 20.0 / frequencies[0], 4001)
    slow_ground = 0.05 * (1.0 - np.cos(np.pi * slow_times / slow_times[-1]))
    slow = tm.analyze_time_history(model, slow_times, base_acceleration_m_s2=slow_ground, **options)
    static_model = replace(
        model, nodal_loads=tuple((-mass * 0.1, 0.0, 0.0) for mass in model.nodal_lumped_masses_kg)
    )
    static_roof = np.asarray(tm.analyze_linear_static(static_model).displacements)[4:6, 0]
    slow_roof = np.asarray(slow.displacements)[-1, 4:6, 0]
    error = np.max(np.abs((slow_roof - static_roof) / static_roof))
    print(f"Slow-ramp roof error against static -M*r*a_g: {100 * error:.4f}%")
    assert error < 0.01, "Slow base excitation should approach the static inertia-load response"


if __name__ == "__main__":
    main()
