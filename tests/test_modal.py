import math

import numpy as np
import pytest

import timoshenko as tm


def uniform_shear_building_frequencies(stories, mass, stiffness):
    """Closed form for a fixed-base uniform shear building with a free top."""
    return [
        2.0 * math.sqrt(stiffness / mass) * math.sin((2 * j - 1) * math.pi / (2 * (2 * stories + 1))) / (2 * math.pi)
        for j in range(1, stories + 1)
    ]


@pytest.mark.parametrize("stories", [1, 2, 5, 12])
def test_uniform_shear_building_matches_closed_form(stories):
    structure = tm.Structure([2.0e5] * stories, [3.0e8] * stories)
    expected = uniform_shear_building_frequencies(stories, 2.0e5, 3.0e8)
    assert structure.natural_frequencies_hz == pytest.approx(expected, rel=1e-10)


def test_two_story_nonuniform_matches_characteristic_equation():
    m1, m2, k1, k2 = 3.0e5, 2.0e5, 5.0e8, 2.5e8
    # det(K - w^2 M) = 0 as a quadratic in w^2
    a = m1 * m2
    b = -(m1 * k2 + m2 * (k1 + k2))
    c = k1 * k2
    roots = sorted(((-b - math.sqrt(b * b - 4 * a * c)) / (2 * a), (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)))
    expected = [math.sqrt(root) / (2 * math.pi) for root in roots]
    assert tm.Structure([m1, m2], [k1, k2]).natural_frequencies_hz == pytest.approx(expected, rel=1e-12)


def test_structure_validation():
    with pytest.raises(ValueError):
        tm.Structure([1.0, 2.0], [1.0])
    with pytest.raises(ValueError):
        tm.Structure([1.0], [-1.0])
    with pytest.raises(ValueError):
        tm.Structure([1.0], [1.0], reference_frequencies_hz=(1.0, 2.0))


def sine_record(frequencies, amplitudes, fs=100.0, n=8192, noise=0.0, seed=0):
    t = np.arange(n) / fs
    signal = sum(a * np.sin(2 * np.pi * f * t) for f, a in zip(frequencies, amplitudes))
    if noise:
        signal = signal + noise * np.random.default_rng(seed).standard_normal(n)
    return tm.SensorData(signal, fs)


def test_peak_picking_recovers_frequencies_within_resolution():
    result = tm.modal.identify(sine_record([2.3, 7.1, 13.4], [1.0, 0.6, 0.3], noise=0.02), max_modes=3)
    assert result.status == "ok"
    assert result.frequencies_hz == pytest.approx([2.3, 7.1, 13.4], abs=result.resolution_hz)
    assert list(result.frequencies_hz) == sorted(result.frequencies_hz)


def test_peak_picking_flags_constant_signal():
    result = tm.modal.identify(tm.SensorData([4.0] * 64, 10.0))
    assert result.status == "insufficient_signal"
    assert result.modes == ()


def test_peak_picking_rejects_bad_bounds():
    with pytest.raises(ValueError):
        tm.modal.identify(sine_record([2.0], [1.0]), min_frequency_hz=5.0, max_frequency_hz=4.0)


def test_fdd_recovers_frequencies_and_mode_shapes():
    fs, n = 100.0, 16384
    t = np.arange(n) / fs
    shape_1, shape_2 = np.array([1.0, 0.8, 0.3]), np.array([0.5, -0.4, 1.0])
    rng = np.random.default_rng(3)
    q1 = np.sin(2 * np.pi * 3.1 * t)
    q2 = 0.7 * np.sin(2 * np.pi * 9.7 * t + 0.4)
    samples = np.outer(q1, shape_1) + np.outer(q2, shape_2) + 0.01 * rng.standard_normal((n, 3))
    data = tm.MultiChannelData(samples, sampling_hz=fs, channel_ids=["a", "b", "c"], units=["g"] * 3)
    result = tm.identify_fdd(data, max_modes=2, nperseg=1024)
    assert result.frequencies_hz == pytest.approx([3.1, 9.7], abs=result.resolution_hz)
    for mode, expected in zip(result.modes, (shape_1, shape_2)):
        estimate = np.array(mode.shape_real) + 1j * np.array(mode.shape_imag)
        mac = abs(np.vdot(estimate, expected)) ** 2 / (np.vdot(estimate, estimate).real * np.dot(expected, expected))
        assert mac > 0.999


def test_fdd_rejects_mixed_units_and_single_segment():
    samples = np.random.default_rng(0).standard_normal((64, 2))
    with pytest.raises(ValueError):
        tm.identify_fdd(tm.MultiChannelData(samples, sampling_hz=10.0, channel_ids=["a", "b"], units=["g", "m/s^2"]))
    with pytest.raises(ValueError):
        tm.identify_fdd(tm.MultiChannelData(samples, sampling_hz=10.0, channel_ids=["a", "b"], units=["g", "g"]), nperseg=64)


def test_uniform_stiffness_loss_is_recovered_by_update():
    structure = tm.Structure([1.0e5] * 3, [2.0e8] * 3)
    scale = 0.81
    damaged = [f * math.sqrt(scale) for f in structure.natural_frequencies_hz]
    result = tm.monitor(structure, sine_record(damaged, [1.0, 0.5, 0.3], n=65536))
    assert result.structure.update_status == "updated"
    assert result.structure.update_scale_factor == pytest.approx(scale, rel=0.01)
    assert result.structure.reference_frequencies_hz == pytest.approx(structure.natural_frequencies_hz)
    assert [c.change_pct for c in result.health.mode_changes] == pytest.approx([-10.0] * 3, abs=0.2)
    assert result.health.status == "evidence_available"


def test_update_does_not_mutate_input_and_rejects_empty_modal():
    structure = tm.Structure([1.0e5], [2.0e8])
    modal = tm.modal.identify(sine_record([7.0], [1.0]))
    updated = tm.update(structure, modal)
    assert structure.update_status == "not_updated"
    assert updated is not structure
    empty = tm.modal.identify(tm.SensorData([0.0] * 32, 10.0))
    with pytest.raises(ValueError):
        tm.update(structure, empty)


def test_monitor_reports_insufficient_evidence_for_flat_signal():
    result = tm.monitor(tm.Structure([1.0e5], [2.0e8]), tm.SensorData([1.0] * 128, 50.0))
    assert result.health.status == "insufficient_evidence"
    assert result.structure.update_status == "not_updated"
    assert result.to_dict()["health"]["mode_changes"] == []


def test_load_sensors_csv_json_and_array(tmp_path):
    csv_path = tmp_path / "acc.csv"
    csv_path.write_text("time,value\n" + "".join(f"{i},{i * 0.5}\n" for i in range(10)))
    json_path = tmp_path / "acc.json"
    json_path.write_text('{"samples": [' + ",".join(str(i * 0.5) for i in range(10)) + "]}")
    from_csv = tm.load_sensors(csv_path, sampling_hz=20.0)
    from_json = tm.load_sensors(json_path, sampling_hz=20.0)
    from_array = tm.load_sensors([i * 0.5 for i in range(10)], sampling_hz=20.0)
    assert from_csv.samples == from_json.samples == from_array.samples
    assert from_csv.channel == "acc"
    with pytest.raises(ValueError):
        tm.load_sensors(csv_path)
    with pytest.raises(ValueError):
        tm.load_sensors(csv_path, sampling_hz=20.0, column="missing")


def test_multichannel_csv_rejects_blank_cells(tmp_path):
    path = tmp_path / "mc.csv"
    path.write_text("a,b\n" + "".join(f"{i},{i}\n" for i in range(9)) + "1,\n")
    with pytest.raises(ValueError):
        tm.load_multichannel_csv(path, columns=["a", "b"], sampling_hz=10.0)


def test_multichannel_data_is_read_only_copy():
    source = np.zeros((16, 2))
    data = tm.MultiChannelData(source, sampling_hz=10.0, channel_ids=["a", "b"], units=["g", "g"])
    source[0, 0] = 99.0
    assert data.samples[0, 0] == 0.0
    with pytest.raises(ValueError):
        data.samples[0, 0] = 1.0
