import pytest

from timoshenko.multichannel import load_multichannel_csv


def test_multichannel_csv_rejects_blank_sample_lines_without_shifting_alignment(
    tmp_path,
):
    path = tmp_path / "gappy.csv"
    path.write_text(
        "a,b\n0,10\n1,11\n2,12\n\n3,13\n4,14\n5,15\n6,16\n7,17\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="CSV line 5 is blank"):
        load_multichannel_csv(path, columns=["a", "b"], sampling_hz=10.0)


def test_multichannel_csv_reports_blank_lines_after_the_header(tmp_path):
    path = tmp_path / "empty-first-sample.csv"
    path.write_text(
        "a,b\n\n0,10\n1,11\n2,12\n3,13\n4,14\n5,15\n6,16\n7,17\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="CSV line 2 is blank"):
        load_multichannel_csv(path, columns=["a", "b"], sampling_hz=10.0)
