"""Focused checks for SSI-COV, EFDD and asynchronous channel alignment."""

import numpy as np
import pytest

from timoshenko.alignment import TimedChannel, align_multichannel
from timoshenko.multichannel import MultiChannelData
from timoshenko.oma import identify_fdd
from timoshenko.session import MonitoringSession
from timoshenko.ssi import identify_ssi
from timoshenko.structure import Structure


def _ar_mode(frequency_hz, damping, sampling_hz, count, rng):
    radius = np.exp(-damping * 2.0 * np.pi * frequency_hz / sampling_hz)
    angle = 2.0 * np.pi * frequency_hz * np.sqrt(1.0 - damping**2) / sampling_hz
    values = np.zeros(count)
    noise = rng.standard_normal(count)
    for index in range(2, count):
        values[index] = (
            2.0 * radius * np.cos(angle) * values[index - 1]
            - radius**2 * values[index - 2]
            + noise[index]
        )
    return values / np.std(values)


def test_ssi_covariance_identifies_stable_noisy_modes_and_shapes():
    fs, count = 100.0, 12_000
    rng = np.random.default_rng(23)
    q1 = _ar_mode(3.2, 0.025, fs, count, rng)
    q2 = _ar_mode(8.1, 0.04, fs, count, rng)
    shape1 = np.array([1.0, 0.55, -0.25])
    shape2 = np.array([0.25, -0.7, 1.0])
    samples = np.outer(q1, shape1) + np.outer(q2, shape2)
    samples += 0.05 * rng.standard_normal(samples.shape)
    data = MultiChannelData(samples, fs, ["a", "b", "c"], ["g"] * 3)
    result = identify_ssi(
        data,
        block_rows=24,
        model_orders=(6, 12, 18, 24, 30),
        min_frequency_hz=1.0,
        max_frequency_hz=15.0,
        min_stable_orders=3,
    )
    assert result.status == "ok"
    assert result.frequencies_hz == pytest.approx([3.2, 8.1], abs=0.2)
    assert all(mode.stable_order_count >= 3 for mode in result.modes)
    assert all(0.0 <= mode.damping_ratio <= 0.5 for mode in result.modes)
    expected = (shape1, shape2)
    for mode, expected_shape in zip(result.modes, expected, strict=True):
        estimated = np.array(mode.shape_real) + 1j * np.array(mode.shape_imag)
        mac = abs(np.vdot(estimated, expected_shape)) ** 2 / (
            np.vdot(estimated, estimated).real * np.dot(expected_shape, expected_shape)
        )
        assert mac > 0.9


def test_ssi_rejects_bad_order_configuration_and_mixed_units():
    values = np.random.default_rng(1).standard_normal((2048, 2))
    data = MultiChannelData(values, 50.0, ["a", "b"], ["g", "g"])
    with pytest.raises(ValueError, match="model_orders"):
        identify_ssi(data, model_orders=(4, 4))
    mixed = MultiChannelData(values, 50.0, ["a", "b"], ["g", "m/s^2"])
    with pytest.raises(ValueError, match="same measurement unit"):
        identify_ssi(mixed)
    many_channels = MultiChannelData(
        np.random.default_rng(2).standard_normal((1024, 16)),
        50.0,
        [f"s{index}" for index in range(16)],
        ["g"] * 16,
    )
    with pytest.raises(ValueError, match="bound SSI memory"):
        identify_ssi(many_channels, block_rows=65)


def test_fdd_efdd_reports_damping_for_stochastic_damped_mode():
    fs, count = 100.0, 32_768
    rng = np.random.default_rng(7)
    response = _ar_mode(4.5, 0.04, fs, count, rng)
    shape = np.array([1.0, -0.5, 0.25])
    data = MultiChannelData(
        np.outer(response, shape) + 0.01 * rng.standard_normal((count, 3)),
        fs,
        ["a", "b", "c"],
        ["g"] * 3,
    )
    result = identify_fdd(
        data,
        nperseg=4096,
        max_modes=1,
        min_frequency_hz=2.0,
        max_frequency_hz=8.0,
        estimate_damping=True,
    )
    assert len(result.modes) == 1
    mode = result.modes[0]
    assert mode.frequency_hz == pytest.approx(4.5, abs=0.15)
    assert mode.damping_ratio is not None
    assert mode.damping_method == "efdd"
    assert mode.damping_ratio == pytest.approx(0.04, abs=0.025)


def test_monitoring_session_accepts_efdd_option_for_multichannel_analysis():
    session = MonitoringSession(
        Structure([1.0e5], [2.0e8]),
        sensor_ids=["a", "b"],
        units=["g", "g"],
        sampling_hz=50.0,
        window_samples=512,
        analysis_options={"nperseg": 128, "estimate_damping": True},
    )
    assert session.buffered_samples_by_sensor == {"a": 0, "b": 0}


def test_alignment_applies_clock_offset_calibration_and_anti_alias_resampling():
    fs, target_fs, count = 100.0, 40.0, 3000
    rng = np.random.default_rng(2)
    t1 = np.arange(count) / fs
    t2 = np.arange(count) / fs - 0.01
    t1 += rng.normal(0.0, 0.0002, count)
    t2 += rng.normal(0.0, 0.0002, count)
    signal1 = np.sin(2.0 * np.pi * 5.0 * t1)
    # Raw channel is half-scale and has a constant sensor offset.
    signal2 = 0.5 * np.sin(2.0 * np.pi * 5.0 * (t2 + 0.01)) + 2.0
    result = align_multichannel(
        (
            TimedChannel("a", "g", t1, signal1),
            TimedChannel("b", "g", t2, signal2),
        ),
        sampling_hz=target_fs,
        time_offsets_s={"b": 0.01},
        calibration_scales={"b": 2.0},
        calibration_offsets={"b": -4.0},
    )
    assert len(result.segments) == 1
    segment = result.segments[0]
    assert segment.data.sampling_hz == target_fs
    assert segment.data.sample_count > 1000
    assert segment.data.samples[:, 0] == pytest.approx(segment.data.samples[:, 1], abs=0.08)


def test_alignment_splits_large_gaps_and_rejects_extrapolation():
    t = np.arange(120) / 20.0
    kept = np.ones(len(t), dtype=bool)
    kept[50:65] = False
    a = TimedChannel("a", "g", t, np.sin(2 * np.pi * 2 * t))
    b = TimedChannel("b", "g", t[kept], np.cos(2 * np.pi * 2 * t[kept]))
    result = align_multichannel((a, b), sampling_hz=20.0, max_gap_s=0.075, sinc_half_width=4)
    assert len(result.segments) == 2
    assert result.dropped_grid_points >= 15
    assert result.segments[0].timestamps_s[-1] < result.segments[1].timestamps_s[0]

    short = TimedChannel("b", "g", t[10:], np.cos(2 * np.pi * 2 * t[10:]))
    overlap = align_multichannel((a, short), sampling_hz=20.0, sinc_half_width=4)
    assert overlap.segments[0].timestamps_s[0] >= t[10]


def test_alignment_validates_sampling_and_input_timestamps():
    t = np.arange(100) / 20.0
    channel = TimedChannel("a", "g", t, t)
    other = TimedChannel("b", "g", t, t)
    with pytest.raises(ValueError, match="cannot exceed"):
        align_multichannel((channel, other), sampling_hz=21.0)
    with pytest.raises(ValueError, match="strictly increasing"):
        TimedChannel("bad", "g", [0, 1, 1, 2, 3, 4, 5, 6], [0] * 8)
