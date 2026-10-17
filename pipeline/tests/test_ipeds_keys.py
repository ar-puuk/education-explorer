"""IPEDS uniqueness keys are derived from the national files, not from one state's rows."""
from types import SimpleNamespace

import duckdb

from nces_pipeline import ipeds_build as ib

COLS = {
    "UNITID": {"name": "unitid", "type": "VARCHAR"},
    "LINE": {"name": "line", "type": "VARCHAR"},
    "SECTOR": {"name": "sector", "type": "VARCHAR"},
    "XLINE": {"name": "line_flag", "type": "VARCHAR", "flag_for": "line"},
}


def _files(tmp_path, monkeypatch, rows_by_year: dict[int, list[str]]):
    files = []
    paths = {}
    for year, rows in rows_by_year.items():
        p = tmp_path / f"f{year}.csv"
        p.write_text("UNITID,LINE,SECTOR,XLINE\n" + "\n".join(rows) + "\n", encoding="utf-8")
        f = SimpleNamespace(year=year)
        files.append(f)
        paths[id(f)] = p
    monkeypatch.setattr(ib, "data_csv", lambda f: paths[id(f)])
    return files


def test_seed_that_is_unique_everywhere_is_kept(tmp_path, monkeypatch):
    files = _files(tmp_path, monkeypatch, {2020: ["1,a,x,", "2,a,y,"]})
    assert ib._extend_key(duckdb.connect(), files, COLS, ["unitid"]) == ["unitid"]


def test_seed_is_widened_when_another_state_has_repeating_rows(tmp_path, monkeypatch):
    # Unit 1 (the "configured state") has one row; unit 2 (another state) has two rows per year.
    files = _files(tmp_path, monkeypatch, {2020: ["1,a,x,", "2,a,y,", "2,b,y,"], 2021: ["1,a,x,", "2,a,y,", "2,b,y,"]})
    key = ib._extend_key(duckdb.connect(), files, COLS, ["unitid"])
    assert key == ["unitid", "line"]


def test_uniqueness_is_checked_within_each_year_file(tmp_path, monkeypatch):
    # The same unit appears once in each year: unique per year file, so no widening is needed.
    files = _files(tmp_path, monkeypatch, {2019: ["1,a,x,"], 2020: ["1,a,x,"]})
    assert ib._extend_key(duckdb.connect(), files, COLS, ["unitid"]) == ["unitid"]


def test_flag_columns_never_join_the_key(tmp_path, monkeypatch):
    files = _files(tmp_path, monkeypatch, {2020: ["1,a,x,P", "1,b,x,R"]})
    key = ib._extend_key(duckdb.connect(), files, COLS, ["unitid"])
    assert "line_flag" not in key and key[0] == "unitid"
