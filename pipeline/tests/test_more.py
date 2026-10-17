import duckdb
import pytest

from nces_pipeline.ccd_legacy_build import _long_rows, normalize
from nces_pipeline.geocode import addr_key, input_address
from nces_pipeline.ipeds_build import years_from_str, years_to_str
from nces_pipeline.ipeds_files import family_of
from nces_pipeline.pss import canonical
from nces_pipeline.schema import SchemaDrift, scaffold
from nces_pipeline.typecheck import check_casts


@pytest.mark.parametrize(
    "name,year,family",
    [
        ("EF2023A", 2023, "efa"), ("EF2005_A", 2005, "efa"), ("F2223_F1A", 2023, "ff1a"), ("F0910_F1A", 2010, "ff1a"),
        ("GR200_24", 2024, "gr200"), ("GR200_20", 2020, "gr200"), ("IC2023_AY", 2023, "icay"), ("SFA9900S", 2000, "sfa"),
        ("FA2000HD", 2000, "hd"), ("DRVEF122023", 2023, "drvef12"), ("S2012_SIS", 2012, "ssis"),
    ],
)
def test_ipeds_family_names(name, year, family):
    assert family_of(name, year) == family


def test_year_ranges_round_trip():
    ys = [2000, 2001, 2002, 2005, 2007, 2008]
    assert years_to_str(ys) == "2000-2002,2005,2007-2008"
    assert years_from_str(years_to_str(ys)) == set(ys)


def test_addr_key_normalizes_and_skips_po_boxes():
    a = addr_key("1199 N. Lakeshore Dr.", "Provo", "ut", "84601-1234")
    b = addr_key("1199 N LAKESHORE DR", "PROVO", "UT", "84601")
    assert a == b == "1199 N LAKESHORE DR|PROVO|UT|84601"
    assert addr_key("PO Box 512", "Eden", "UT", "84310") is None
    assert addr_key("", "Eden", "UT", "84310") is None
    assert input_address(a) == "1199 N LAKESHORE DR, PROVO, UT 84601"


def test_legacy_suffix_is_stripped_only_when_the_file_uses_it(tmp_path):
    con = duckdb.connect()
    p98 = tmp_path / "s98.parquet"
    con.execute(f"COPY (SELECT 'a' AS NCESSCH, 'x' AS SCHNAM98, '5' AS G1298, '1' AS AMPKM98) TO '{p98.as_posix()}'")
    names = normalize(con, p98, 1998, "SCHNAM")
    assert {"SCHNAM", "G12", "AMPKM"} <= set(names)
    p10 = tmp_path / "s10.parquet"  # 2010: no suffix convention, so grade 10 must stay G10
    con.execute(f"COPY (SELECT 'a' AS NCESSCH, 'x' AS SCHNAM, '5' AS G10, '1' AS AMPKM) TO '{p10.as_posix()}'")
    assert "G10" in normalize(con, p10, 2010, "SCHNAM")


def test_legacy_membership_columns_are_recognized():
    names = {c: c for c in ["AMPKM", "WHKGF", "BL01U", "PK", "G12", "MEMBER", "AM", "WHITE", "NCESSCH"]}
    by = {r["source"]: r for r in _long_rows(names, "school")}
    assert by["AMPKM"]["race"] == "American Indian or Alaska Native" and by["AMPKM"]["sex"] == "Male"
    assert by["BL01U"]["sex"] == "Not Specified" and by["BL01U"]["grade"] == "Grade 1"
    assert by["G12"]["total_indicator"] == "Subtotal 4 - By Grade"
    assert by["MEMBER"]["total_indicator"] == "Education Unit Total"
    assert "NCESSCH" not in by


def test_type_drift_guard_fails_on_text_in_numeric_column(tmp_path):
    con = duckdb.connect()
    p = tmp_path / "t.parquet"
    con.execute(f"COPY (SELECT * FROM (VALUES ('1', '10'), ('2', 'abc'), (NULL, 'M')) t(a, b)) TO '{p.as_posix()}'")
    check_casts(con, p, [("a", "BIGINT")], "x", "hint")  # fine
    with pytest.raises(SchemaDrift, match="TYPE DRIFT"):
        check_casts(con, p, [("b", "BIGINT")], "x", "hint")


def test_pss_year_suffixed_names_share_one_canonical_name():
    assert canonical("LATITUDE24") == ("lat", True) and canonical("LATITUDE") == ("lat", True)
    assert canonical("ULOCALE12")[0] == "ulocale" and canonical("PCNTY24")[0] == "county_fips"
    assert canonical("P305") == ("p305", False) and canonical("PPIN") == ("ppin", False)


def test_scaffold_copies_previous_year_and_marks_new_columns(tmp_path, monkeypatch):
    from nces_pipeline import schema

    monkeypatch.setattr(schema, "SCHEMAS", tmp_path)
    d = tmp_path / "ccd" / "t"
    d.mkdir(parents=True)
    (d / "2020.yml").write_text("source: ccd\ntopic: t\nyear: 2020\ncolumns:\n  A: {name: a}\n  GONE: {name: gone}\n")
    p = scaffold("ccd", "t", 2021, ["A", "NEW"])
    text = p.read_text()
    assert "name: a" in text and "TODO_new" in text and "GONE" in text.split("\n")[1]
