"""Closed-form checks for the analytic engineering primitives.

Expected values come from independent derivations (unit-load integration,
stress-tensor eigenvalues, complex transfer functions) rather than from the
same expressions used in the implementation.
"""

import math

import numpy as np
import pytest

import timoshenko as tm


def simpson(values, x):
    h = (x[-1] - x[0]) / (len(x) - 1)
    return h / 3.0 * (values[0] + values[-1] + 4.0 * values[1:-1:2].sum() + 2.0 * values[2:-1:2].sum())


E, G, INERTIA, AREA, KAPPA, SPAN = 200e9, 77e9, 8.0e-6, 6.0e-3, 5.0 / 6.0, 3.2


def unit_load_deflection(moment, unit_moment, shear, unit_shear):
    x = np.linspace(0.0, SPAN, 20001)
    bending = simpson(moment(x) * unit_moment(x), x) / (E * INERTIA)
    shear_term = simpson(shear(x) * unit_shear(x), x) / (KAPPA * G * AREA)
    return bending, shear_term


def half(x, left, right):
    return np.where(x < SPAN / 2.0, left(x), right(x))


BEAM_CASES = [
    (
        tm.cantilever_tip_load, 12e3,
        lambda P: (lambda x: -P * (SPAN - x), lambda x: -(SPAN - x), lambda x: P + 0 * x, lambda x: 1 + 0 * x),
    ),
    (
        tm.cantilever_uniform_load, 4e3,
        lambda w: (lambda x: -w * (SPAN - x) ** 2 / 2, lambda x: -(SPAN - x), lambda x: w * (SPAN - x), lambda x: 1 + 0 * x),
    ),
    (
        tm.simply_supported_midpoint_load, 12e3,
        lambda P: (
            lambda x: P * half(x, lambda s: s / 2, lambda s: (SPAN - s) / 2),
            lambda x: half(x, lambda s: s / 2, lambda s: (SPAN - s) / 2),
            lambda x: P * half(x, lambda s: 0.5 + 0 * s, lambda s: -0.5 + 0 * s),
            lambda x: half(x, lambda s: 0.5 + 0 * s, lambda s: -0.5 + 0 * s),
        ),
    ),
    (
        tm.simply_supported_uniform_load, 4e3,
        lambda w: (
            lambda x: w * x * (SPAN - x) / 2,
            lambda x: half(x, lambda s: s / 2, lambda s: (SPAN - s) / 2),
            lambda x: w * (SPAN / 2 - x),
            lambda x: half(x, lambda s: 0.5 + 0 * s, lambda s: -0.5 + 0 * s),
        ),
    ),
]


@pytest.mark.parametrize("function, load, fields", BEAM_CASES, ids=lambda item: getattr(item, "__name__", ""))
def test_beam_deflection_matches_unit_load_integration(function, load, fields):
    bending, shear = unit_load_deflection(*fields(load))
    result = function(load, SPAN, E, INERTIA, shear_modulus_pa=G, area_m2=AREA)
    assert result.bending_m == pytest.approx(bending, rel=1e-6)
    assert result.shear_m == pytest.approx(shear, rel=1e-6)
    assert result.total_m == pytest.approx(bending + shear, rel=1e-6)


def test_beam_shear_term_is_optional_but_needs_both_inputs():
    assert tm.cantilever_tip_load(1e3, 2.0, E, INERTIA).shear_m == 0.0
    with pytest.raises(ValueError):
        tm.cantilever_tip_load(1e3, 2.0, E, INERTIA, shear_modulus_pa=G)
    with pytest.raises(ValueError):
        tm.cantilever_tip_load(1e3, -2.0, E, INERTIA)


def test_rectangle_and_circle_sections():
    rect = tm.rectangle_section(0.2, 0.5)
    assert rect.area_m2 == pytest.approx(0.1)
    assert rect.second_moment_y_m4 == pytest.approx(0.2 * 0.5**3 / 12)
    assert rect.section_modulus_y_m3 == pytest.approx(0.2 * 0.5**2 / 6)
    circle = tm.solid_circle_section(0.3)
    assert circle.second_moment_y_m4 == pytest.approx(math.pi * 0.15**4 / 4)
    tube = tm.circular_tube_section(0.3, 0.2)
    assert tube.second_moment_y_m4 == pytest.approx(math.pi * (0.15**4 - 0.1**4) / 4)
    with pytest.raises(ValueError):
        tm.circular_tube_section(0.2, 0.2)


def test_i_section_equals_outer_rectangle_minus_side_voids():
    b, h, tw, tf = 0.2, 0.4, 0.01, 0.015
    section = tm.i_section(b, h, tw, tf)
    void_w, void_h = (b - tw), h - 2 * tf
    assert section.area_m2 == pytest.approx(b * h - void_w * void_h)
    assert section.second_moment_y_m4 == pytest.approx(b * h**3 / 12 - void_w * void_h**3 / 12)
    assert section.second_moment_z_m4 == pytest.approx(2 * tf * b**3 / 12 + void_h * tw**3 / 12)
    with pytest.raises(ValueError):
        tm.i_section(b, h, b, tf)


def test_rectangular_tube_equals_outer_minus_inner_rectangle():
    b, h, t = 0.15, 0.25, 0.008
    section = tm.rectangular_tube_section(b, h, t)
    bi, hi = b - 2 * t, h - 2 * t
    assert section.area_m2 == pytest.approx(b * h - bi * hi)
    assert section.second_moment_y_m4 == pytest.approx((b * h**3 - bi * hi**3) / 12)
    assert section.second_moment_z_m4 == pytest.approx((h * b**3 - hi * bi**3) / 12)
    assert section.section_modulus_z_m3 == pytest.approx(section.second_moment_z_m4 / (b / 2))


def test_elementary_mechanics():
    assert tm.axial_stress(-1e5, 0.01) == pytest.approx(-1e7)
    assert tm.bending_stress(2e4, 1e-3) == pytest.approx(2e7)
    assert tm.rectangular_max_shear_stress(3e4, 0.02) == pytest.approx(1.5 * 3e4 / 0.02)
    assert tm.axial_strain(200e6, 200e9) == pytest.approx(1e-3)
    assert tm.thermal_strain(12e-6, -30.0) == pytest.approx(-3.6e-4)
    assert tm.youngs_modulus_from_shear(80e9, 0.25) == pytest.approx(200e9)
    with pytest.raises(ValueError):
        tm.youngs_modulus_from_shear(80e9, 0.5)


def test_circular_torsion_polar_moment_is_twice_the_second_moment():
    result = tm.circular_shaft_torsion(5e3, 2.0, 80e9, 0.08, 0.05)
    inertia = tm.circular_tube_section(0.08, 0.05).second_moment_y_m4
    assert result.polar_moment_m4 == pytest.approx(2 * inertia)
    assert result.maximum_shear_stress_pa == pytest.approx(5e3 * 0.04 / (2 * inertia))
    assert result.twist_rad == pytest.approx(5e3 * 2.0 / (80e9 * 2 * inertia))


def test_euler_buckling_and_slenderness():
    base = tm.euler_critical_load(200e9, 1e-6, 3.0)
    assert base == pytest.approx(math.pi**2 * 200e9 * 1e-6 / 9.0)
    assert tm.euler_critical_load(200e9, 1e-6, 3.0, effective_length_factor=2.0) == pytest.approx(base / 4)
    assert tm.slenderness_ratio(3.0, 1.0, 4e-3, 1e-6) == pytest.approx(3.0 / math.sqrt(1e-6 / 4e-3))


@pytest.mark.parametrize("sx, sy, txy", [(80e6, -20e6, 35e6), (0.0, 0.0, 50e6), (-40e6, -40e6, 0.0), (10e6, 90e6, -25e6)])
def test_plane_stress_matches_tensor_eigenvalues(sx, sy, txy):
    principal = np.linalg.eigvalsh(np.array([[sx, txy], [txy, sy]]))
    result = tm.plane_stress(sx, sy, txy)
    assert result.principal_max_pa == pytest.approx(principal[1], abs=1.0)
    assert result.principal_min_pa == pytest.approx(principal[0], abs=1.0)
    assert result.maximum_in_plane_shear_pa == pytest.approx((principal[1] - principal[0]) / 2, abs=1.0)
    s1, s2, s3 = principal[1], principal[0], 0.0
    von_mises = math.sqrt(((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2) / 2)
    assert result.von_mises_pa == pytest.approx(von_mises, abs=1.0)


def test_thin_wall_cylinder():
    result = tm.thin_wall_cylinder_stress(2e6, 0.5, 0.01)
    assert result.hoop_stress_pa == pytest.approx(1e8)
    assert result.longitudinal_stress_pa == pytest.approx(5e7)
    assert result.thickness_to_mean_radius_ratio == pytest.approx(0.02)


def test_sdof_vibration_matches_complex_transfer_function():
    m, k, c, force, freq = 250.0, 4e5, 900.0, 120.0, 5.5
    omega = 2 * math.pi * freq
    transfer = 1.0 / complex(k - m * omega**2, c * omega)
    result = tm.harmonic_response(force, freq, m, k, c)
    assert result.displacement_amplitude_m == pytest.approx(abs(force * transfer))
    assert result.phase_lag_rad == pytest.approx(-math.atan2(transfer.imag, transfer.real))
    assert tm.natural_frequency_hz(m, k) == pytest.approx(math.sqrt(k / m) / (2 * math.pi))
    assert tm.damping_ratio(m, k, c) == pytest.approx(c / (2 * math.sqrt(k * m)))
    with pytest.raises(ValueError):
        tm.harmonic_response(1.0, tm.natural_frequency_hz(m, k), m, k, 0.0)


def test_rayleigh_equal_targets_match_closed_form():
    f1, f2, zeta = 1.2, 7.5, 0.03
    w1, w2 = 2 * math.pi * f1, 2 * math.pi * f2
    result = tm.rayleigh_damping_coefficients(f2, zeta, f1, zeta)
    assert result.alpha_mass_s_inv == pytest.approx(2 * zeta * w1 * w2 / (w1 + w2))
    assert result.beta_stiffness_s == pytest.approx(2 * zeta / (w1 + w2))
    assert result.modal_damping_ratio(f1) == pytest.approx(zeta)
    assert result.modal_damping_ratio(f2) == pytest.approx(zeta)
    assert result.modal_damping_ratio(math.sqrt(f1 * f2)) < zeta


def test_rayleigh_rejects_non_passive_and_degenerate_targets():
    with pytest.raises(ValueError):
        tm.rayleigh_damping_coefficients(1.0, 0.05, 10.0, 0.001)
    with pytest.raises(ValueError):
        tm.rayleigh_damping_coefficients(2.0, 0.02, 2.0, 0.03)
