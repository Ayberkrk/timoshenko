import pytest

from timoshenko.csv_source import CSVObservationSource, CSVSourceError

HEADER = "timestamp,sensor_id,name,unit,value,quality,asset_id\n"
ROW = "0,a,acc,g,1,good,\n"


@pytest.mark.parametrize("batch_size", [0, -1, 4097, True, 1.5])
def test_rejects_invalid_batch_size(tmp_path, batch_size):
    with pytest.raises(ValueError, match="batch_size must be an integer between 1 and 4096"):
        CSVObservationSource(tmp_path / "unused.csv", batch_size=batch_size)


@pytest.mark.parametrize(
    "options",
    [
        {"timestamp_column": ""},
        {"name_column": "  "},
        {"value_column": "timestamp"},
        {"quality_column": " sensor_id "},
    ],
)
def test_rejects_empty_or_duplicate_configured_columns(tmp_path, options):
    with pytest.raises(
        ValueError, match="configured CSV column names must be non-empty and distinct"
    ):
        CSVObservationSource(tmp_path / "unused.csv", **options)


@pytest.mark.parametrize("source_id", ["", " \t"])
def test_rejects_empty_source_id(tmp_path, source_id):
    with pytest.raises(ValueError, match="source_id must be non-empty"):
        CSVObservationSource(tmp_path / "unused.csv", source_id=source_id)


def test_read_requires_open(tmp_path):
    source = CSVObservationSource(tmp_path / "unused.csv")
    with pytest.raises(RuntimeError, match=r"open\(\) must be called before read_batch\(\)"):
        source.read_batch()


def test_duplicate_open_preserves_current_reader(tmp_path):
    path = tmp_path / "observations.csv"
    path.write_text(HEADER + ROW + "1,a,acc,g,2,good,\n", encoding="utf-8")
    source = CSVObservationSource(path, batch_size=1)
    source.open()
    try:
        assert source.read_batch().observations[0].value == 1
        with pytest.raises(RuntimeError, match="CSV observation source is already open"):
            source.open()
        assert source.read_batch().observations[0].value == 2
        assert source.read_batch() is None
    finally:
        source.close()


def test_missing_file_can_be_created_and_opened_after_failure(tmp_path):
    path = tmp_path / "missing.csv"
    source = CSVObservationSource(path)
    with pytest.raises(CSVSourceError, match=r"cannot open observation CSV .*missing\.csv:"):
        source.open()
    path.write_text(HEADER + ROW, encoding="utf-8")
    source.open()
    try:
        assert source.read_batch().count == 1
    finally:
        source.close()


@pytest.mark.parametrize(
    "header, message",
    [
        ("", "CSV must contain a header row with non-empty column names"),
        ("timestamp, ,value\n", "CSV must contain a header row with non-empty column names"),
        (HEADER.rstrip("\n") + ",value\n", "CSV header contains duplicate column names"),
        (
            "timestamp,sensor_id,name,unit,value\n",
            "CSV is missing configured columns: asset_id, quality",
        ),
    ],
)
def test_invalid_header_can_be_corrected_and_reopened(tmp_path, header, message):
    path = tmp_path / "header.csv"
    path.write_text(header, encoding="utf-8")
    source = CSVObservationSource(path)
    with pytest.raises(CSVSourceError, match=message):
        source.open()
    path.write_text(HEADER + ROW, encoding="utf-8")
    source.open()
    try:
        assert source.read_batch().count == 1
    finally:
        source.close()


@pytest.mark.parametrize(
    "timestamp, message",
    [
        ("not-a-time", "timestamp must be Unix seconds or timezone-aware ISO-8601"),
        ("nan", "timestamp must be finite"),
        ("inf", "timestamp must be finite"),
        ("-inf", "timestamp must be finite"),
    ],
)
def test_rejects_invalid_timestamp_with_row_context(tmp_path, timestamp, message):
    path = tmp_path / "timestamp.csv"
    path.write_text(HEADER + f"{timestamp},a,acc,g,1,good,\n", encoding="utf-8")
    source = CSVObservationSource(path)
    source.open()
    try:
        with pytest.raises(CSVSourceError, match=f"invalid observation near CSV line 2: {message}"):
            source.read_batch()
    finally:
        source.close()


@pytest.mark.parametrize("column", ["timestamp", "sensor_id", "name", "unit", "value", "quality"])
@pytest.mark.parametrize("empty", ["", " \t"])
def test_rejects_empty_required_cell(tmp_path, column, empty):
    fields = dict(zip(HEADER.strip().split(","), ROW.strip().split(","), strict=True))
    fields[column] = empty
    path = tmp_path / "empty-cell.csv"
    path.write_text(HEADER + ",".join(fields.values()) + "\n", encoding="utf-8")
    source = CSVObservationSource(path)
    source.open()
    try:
        with pytest.raises(
            CSVSourceError,
            match=f"invalid observation near CSV line 2: '{column}' must not be empty",
        ):
            source.read_batch()
    finally:
        source.close()


def test_rejects_malformed_csv_row(tmp_path):
    path = tmp_path / "malformed.csv"
    path.write_text(HEADER + '0,a,"unterminated\n', encoding="utf-8")
    source = CSVObservationSource(path)
    source.open()
    try:
        with pytest.raises(
            CSVSourceError, match=r"malformed CSV near line \d+: unexpected end of data"
        ):
            source.read_batch()
    finally:
        source.close()


def test_skips_empty_rows_without_consuming_batch_sequence(tmp_path):
    path = tmp_path / "blank-row.csv"
    path.write_text(HEADER + ",,,,,,\n" + ROW, encoding="utf-8")
    source = CSVObservationSource(path, source_id="replay", batch_size=1)
    source.open()
    try:
        batch = source.read_batch()
        assert batch.count == 1
        assert batch.batch_id == "replay:rows:1-1"
        assert batch.observations[0].metadata["csv_line"] == 3
        assert source.read_batch() is None
    finally:
        source.close()
