"""Small, SI-unit examples for the reusable Timoshenko calculations."""

import timoshenko as tm


def main() -> None:
    section = tm.rectangle_section(width_m=0.30, height_m=0.50)
    normal_stress = tm.axial_stress(force_n=30_000.0, area_m2=section.area_m2)
    beam = tm.cantilever_tip_load(
        load_n=2_000.0,
        span_m=3.0,
        youngs_modulus_pa=30e9,
        second_moment_m4=section.second_moment_y_m4,
        shear_modulus_pa=12.5e9,
        area_m2=section.area_m2,
    )
    shaft = tm.circular_shaft_torsion(
        torque_nm=500.0,
        length_m=2.0,
        shear_modulus_pa=80e9,
        outer_diameter_m=0.04,
    )
    column_load = tm.euler_critical_load(
        youngs_modulus_pa=200e9,
        second_moment_m4=section.second_moment_y_m4,
        length_m=3.0,
        effective_length_factor=1.0,
    )
    stress_state = tm.plane_stress(80e6, 20e6, 10e6)
    frequency = tm.natural_frequency_hz(mass_kg=1_000.0, stiffness_n_m=2e6)

    print(f"Rectangle area: {section.area_m2:.4f} m^2")
    print(f"Axial stress: {normal_stress / 1e6:.3f} MPa")
    print(f"Cantilever tip deflection: {beam.total_m * 1e3:.3f} mm")
    print(f"Circular shaft max shear: {shaft.maximum_shear_stress_pa / 1e6:.3f} MPa")
    print(f"Ideal Euler critical load: {column_load / 1e3:.1f} kN")
    print(f"Plane-stress von Mises equivalent: {stress_state.von_mises_pa / 1e6:.3f} MPa")
    print(f"SDOF natural frequency: {frequency:.3f} Hz")


if __name__ == "__main__":
    main()
