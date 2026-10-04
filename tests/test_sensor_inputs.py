"""Validation and file input coverage for sensor observations."""

import numpy as np
import pytest

from timoshenko.multichannel import MultiChannelData, load_multichannel_csv
from timoshenko.sensors import SensorData, load_sensors


@pytest.mark.parametrize("sampling_hz", [0.0, -1.0, float("nan"), float("inf")])
def test_sensor_data_rejects_invalid_sampling_frequency(sampling_hz):
    with pytest.raises(ValueError, match="sampling_hz must be finite and greater than zero"):
        SensorData([0.0] * 8, sampling_hz)


def test_sensor_data_rejects_short_or_non_finite_samples():
    with pytest.raises(ValueError, match="at least 8 numeric samples are required"):
        SensorData([0.0] * 7, 10.0)
    with pytest.raises(ValueError, match="sensor samples must all be finite numeric values"):
        SensorData([0.0] * 7 + [float("nan")], 10.0)


def test_sensor_data_validates_timestamps():
    with pytest.raises(ValueError, match="timestamps must have one entry per sample"):
        SensorData([0.0] * 8, 10.0, timestamps=(0.0,))
    with pytest.raises(ValueError, match="timestamps must be finite"):
        SensorData(
            [0.0] * 8,
            10.0,
            timestamps=(0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, float("inf")),
        )
    with pytest.raises(ValueError, match="timestamps must be strictly increasing"):
        SensorData([0.0] * 8, 10.0, timestamps=tuple(range(7)) + (5.0,))
    assert SensorData([0.0] * 8, 4.0).duration_seconds == 2.0


def test_load_sensors_accepts_existing_data_only_with_matching_frequency():
    data = SensorData(range(8), 10.0)
    assert load_sensors(data) is data
    assert load_sensors(data, sampling_hz=10.0) is data
    with pytest.raises(ValueError, match="sampling_hz conflicts with the supplied SensorData"):
        load_sensors(data, sampling_hz=20.0)


def test_load_sensors_parses_csv_headers_values_and_source_names(tmp_path):
    path = tmp_path / "reading.CSV"
    path.write_text("other,value\n0,1\n1,2\n2,3\n3,4\n4,5\n5,6\n6,7\n7,8\n", encoding="utf-8")
    data = load_sensors(path, sampling_hz=5.0)
    assert data.samples == tuple(float(i) for i in range(1, 9))
    assert data.channel == "reading"
    assert (
        load_sensors(path, sampling_hz=5.0, column="value", channel="explicit").channel
        == "explicit"
    )


def test_load_sensors_rejects_bad_csv_values_with_line_numbers(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("value\n1\n2\n3\n4\n5\n6\n7\nnope\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"line 9 is not numeric: 'nope'"):
        load_sensors(path, sampling_hz=10.0)
    path.write_text("value\n1\n2\n3\n4\n5\n6\n7\ninf\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 9 is not finite"):
        load_sensors(path, sampling_hz=10.0)


def test_load_sensors_reads_json_objects_and_json_lines(tmp_path):
    object_path = tmp_path / "object.json"
    object_path.write_text('{"accel": [0,1,2,3,4,5,6,7]}', encoding="utf-8")
    assert load_sensors(object_path, sampling_hz=2.0, column="accel").samples == tuple(
        float(i) for i in range(8)
    )
    rows_path = tmp_path / "rows.json"
    rows_path.write_text(
        '[{"value":0},{"value":1},{"value":2},{"value":3},{"value":4},{"value":5},{"value":6},{"value":7}]',
        encoding="utf-8",
    )
    assert load_sensors(rows_path, sampling_hz=2.0).samples == tuple(float(i) for i in range(8))
    lines_path = tmp_path / "lines.jsonl"
    lines_path.write_text("\n".join('{"value":%d}' % i for i in range(8)), encoding="utf-8")
    assert load_sensors(lines_path, sampling_hz=2.0).samples == tuple(float(i) for i in range(8))


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            '{"other": [1]}',
            "JSON object must contain 'samples' or the selected channel key",
        ),
        ('{"samples": "wrong"}', "JSON sensor data must be an array"),
        ('[{"other": 1}]', "JSON sample 1 has no 'value' value"),
        ('["bad"]', "sensor input line 1 is not numeric: 'bad'"),
        ('[1,2,3,4,5,6,7,"nan"]', "sensor input line 8 is not finite"),
    ],
)
def test_load_sensors_rejects_invalid_json_shapes_and_values(tmp_path, payload, message):
    path = tmp_path / "invalid.json"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_sensors(path, sampling_hz=10.0)


def test_load_sensors_rejects_unsupported_source_and_missing_frequency(tmp_path):
    unsupported = tmp_path / "sensors.txt"
    unsupported.write_text("0", encoding="utf-8")
    with pytest.raises(ValueError, match=r"sensor source must be a \.csv, \.json, or \.jsonl file"):
        load_sensors(unsupported, sampling_hz=10.0)
    with pytest.raises(ValueError, match="sampling_hz is required for sensor input"):
        load_sensors([0.0] * 8)


def test_multichannel_data_validates_shape_and_channel_limits():
    args = {"sampling_hz": 10.0, "channel_ids": ["a", "b"], "units": ["g", "g"]}
    with pytest.raises(ValueError, match="samples must be a 2D array shaped"):
        MultiChannelData(np.zeros(8), **args)
    with pytest.raises(ValueError, match="at least 8 samples and 2 channels are required"):
        MultiChannelData(np.zeros((7, 2)), **args)
    with pytest.raises(ValueError, match="at least 8 samples and 2 channels are required"):
        MultiChannelData(np.zeros((8, 1)), 10.0, ["a"], ["g"])
    with pytest.raises(ValueError, match="at most 32 channels are accepted"):
        MultiChannelData(np.zeros((8, 33)), 10.0, [str(i) for i in range(33)], ["g"] * 33)


@pytest.mark.parametrize(
    ("channel_ids", "units", "message"),
    [
        (["a"], ["g", "g"], "channel_ids and units must have one entry per channel"),
        (["a", "a"], ["g", "g"], "channel_ids must be non-empty and unique"),
        (["a", " "], ["g", "g"], "channel_ids must be non-empty and unique"),
        (["a", "b"], ["g"], "channel_ids and units must have one entry per channel"),
        (["a", "b"], ["g", " "], "units must be non-empty"),
    ],
)
def test_multichannel_data_validates_channel_metadata(channel_ids, units, message):
    with pytest.raises(ValueError, match=message):
        MultiChannelData(np.zeros((8, 2)), 10.0, channel_ids, units)


@pytest.mark.parametrize("sampling_hz", [0.0, -1.0, float("nan"), float("inf")])
def test_multichannel_data_rejects_invalid_frequency(sampling_hz):
    with pytest.raises(ValueError, match="sampling_hz must be finite and greater than zero"):
        MultiChannelData(np.zeros((8, 2)), sampling_hz, ["a", "b"], ["g", "g"])


def test_multichannel_data_rejects_non_finite_samples():
    values = np.zeros((8, 2))
    values[-1, -1] = float("nan")
    with pytest.raises(ValueError, match="all sensor samples must be finite"):
        MultiChannelData(values, 10.0, ["a", "b"], ["g", "g"])


def test_multichannel_csv_validates_columns_units_ids_and_headers(tmp_path):
    path = tmp_path / "channels.csv"
    path.write_text("a,b\n" + "".join(f"{i},{i + 1}\n" for i in range(8)), encoding="utf-8")
    data = load_multichannel_csv(path, columns=["a", "b"], sampling_hz=10.0)
    assert data.channel_ids == ("a", "b")
    assert data.units == ("unknown", "unknown")
    assert data.samples[0].tolist() == [0.0, 1.0]
    with pytest.raises(
        ValueError,
        match="columns must contain at least two distinct non-empty CSV headings",
    ):
        load_multichannel_csv(path, columns=["a", "a"], sampling_hz=10.0)
    with pytest.raises(ValueError, match="units must contain one entry per selected column"):
        load_multichannel_csv(path, columns=["a", "b"], sampling_hz=10.0, units=["g"])
    with pytest.raises(
        ValueError,
        match="channel_ids must contain one distinct, non-empty id per selected column",
    ):
        load_multichannel_csv(
            path, columns=["a", "b"], sampling_hz=10.0, channel_ids=["same", "same"]
        )
    with pytest.raises(ValueError, match=r"CSV columns not found: \['missing'\]"):
        load_multichannel_csv(path, columns=["a", "missing"], sampling_hz=10.0)


@pytest.mark.parametrize(
    ("bad_value", "message"),
    [
        ("", "CSV row 10 has a missing/non-numeric value in 'b'"),
        ("not-a-number", "CSV row 10 has a missing/non-numeric value in 'b'"),
        ("nan", "CSV row 10 has a non-finite value in 'b'"),
    ],
)
def test_multichannel_csv_rejects_invalid_cells_with_row_and_column(tmp_path, bad_value, message):
    path = tmp_path / "bad.csv"
    path.write_text(
        "a,b\n" + "".join(f"{i},{i}\n" for i in range(8)) + f"8,{bad_value}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=message):
        load_multichannel_csv(path, columns=["a", "b"], sampling_hz=10.0)
