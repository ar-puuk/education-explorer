"""Derived outputs: school metrics, state reference bands, year summary, district index."""
import json

import duckdb

from nces_pipeline import derived


def _write(base, rel, select_sql):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    duckdb.connect().execute(f"COPY ({select_sql}) TO '{p.as_posix()}' (FORMAT PARQUET)")


def _fixture(base, n2022=12):
    # 2022: n2022 schools; 2021: 3 schools (too few for a reference band)
    ids = [f"s{i:02d}" for i in range(n2022)]
    d22 = " UNION ALL ".join(f"SELECT 2022 AS year, '{i}' AS ncessch, 'L1' AS leaid, 'Open' AS status, 'Elementary' AS level" for i in ids)
    d21 = " UNION ALL ".join(f"SELECT 2021 AS year, '{i}' AS ncessch, 'L1' AS leaid, 'Open' AS status, 'Elementary' AS level" for i in ids[:3])
    _write(base, "ccd/school_directory/2022.parquet", d22 + " UNION ALL SELECT 2022, 'closed', 'L1', 'Closed', 'Elementary'")
    _write(base, "ccd/school_directory/2021.parquet", d21)
    mem = " UNION ALL ".join(f"SELECT 2022 AS year, '{i}' AS ncessch, 'Education Unit Total' AS total_indicator, {100 + k * 10} AS student_count" for k, i in enumerate(ids))
    _write(base, "ccd/membership/2022.parquet", mem)
    _write(base, "ccd/membership/2021.parquet", "SELECT 2021 AS year, 's00' AS ncessch, 'Education Unit Total' AS total_indicator, 100 AS student_count")
    stf = " UNION ALL ".join(f"SELECT 2022 AS year, '{i}' AS ncessch, 'Education Unit Total' AS total_indicator, {5.0 if k else 0.0}::DOUBLE AS teachers" for k, i in enumerate(ids))
    _write(base, "ccd/staff/2022.parquet", stf)
    lun = []
    for k, i in enumerate(ids):
        lun.append(f"SELECT 2022 AS year, '{i}' AS ncessch, 'Free and Reduced-price Lunch Table' AS data_group, 'Category Set A' AS total_indicator, 'Free lunch qualified' AS lunch_program, 20 AS student_count")
        if k != 1:  # school s01 lacks the reduced-price row
            lun.append(f"SELECT 2022 AS year, '{i}' AS ncessch, 'Free and Reduced-price Lunch Table' AS data_group, 'Category Set A' AS total_indicator, 'Reduced-price lunch qualified' AS lunch_program, 10 AS student_count")
    _write(base, "ccd/lunch/2022.parquet", " UNION ALL ".join(lun))
    return ids


def test_school_metrics_values_and_nulls(tmp_path):
    ids = _fixture(tmp_path)
    assert derived.build_school_metrics(tmp_path) > 0
    con = duckdb.connect()
    rows = {r[0]: r for r in con.execute(
        f"SELECT ncessch, enrollment, teachers_fte, students_per_teacher, frl_count, frl_share FROM read_parquet('{(tmp_path / 'derived/school_metrics/2022.parquet').as_posix()}')").fetchall()}
    assert rows["s00"][3] is None  # zero teachers: no ratio
    assert rows["s02"][1] == 120 and rows["s02"][3] == 24.0  # 120 / 5
    assert rows["s01"][4] is None and rows["s01"][5] is None  # one lunch row missing: share is unknown, not zero
    assert rows["s02"][4] == 30 and rows["s02"][5] == round(30 / 120, 4)
    prof = con.execute(f"SELECT years, enrollment FROM read_parquet('{(tmp_path / 'derived/school_profile.parquet').as_posix()}') WHERE ncessch = 's00'").fetchone()
    assert prof[0] == [2021, 2022] and prof[1] == [100, 100]
    assert len(ids) == 12


def test_reference_band_needs_enough_schools_and_skips_closed(tmp_path):
    _fixture(tmp_path)
    derived.build_school_metrics(tmp_path)
    ref = derived.build_state_reference(tmp_path)
    enr = ref["metrics"]["enrollment"]["years"]
    assert "2022" in enr and "2021" not in enr  # 2021 has only 3 schools
    assert enr["2022"]["n"] == 12  # the closed school is not counted
    assert enr["2022"]["p25"] <= enr["2022"]["median"] <= enr["2022"]["p75"]
    assert json.loads((tmp_path / "meta/state_reference.json").read_text(encoding="utf-8"))["min_n"] == derived.MIN_N


def test_year_summary_and_districts_index(tmp_path):
    geo = tmp_path / "geo"
    geo.mkdir(parents=True)
    (geo / "points_public.json").write_text(json.dumps({
        "years": [2021, 2022], "statuses": ["Closed", "Open"],
        "schools": [{"years": [2021, 2022], "status": [1, 0]}, {"years": [2022], "status": [1]}]}), encoding="utf-8")
    (geo / "points_college.json").write_text(json.dumps({"years": [2022], "institutions": [{"years": [2022], "active": [1]}]}), encoding="utf-8")
    (geo / "points_private.json").write_text(json.dumps({"years": [2021], "schools": [{"years": [2021]}]}), encoding="utf-8")
    s = derived.build_year_summary(tmp_path)
    assert s["public"]["2022"]["mapped"] == 2 and s["public"]["2022"]["operating"] == 1
    assert s["public"]["2021"]["operating"] == 1
    assert s["college"]["2022"] == {"mapped": 1, "active": 1}
    assert s["private"]["2021"]["mapped"] == 1 and s["private_survey_years"] == [2021]

    _write(tmp_path, "ccd/district_directory/2021.parquet", "SELECT 2021 AS year, '1' AS leaid, 'Old Name' AS lea_name")
    _write(tmp_path, "ccd/district_directory/2022.parquet", "SELECT 2022 AS year, '1' AS leaid, 'New Name' AS lea_name UNION ALL SELECT 2022, '2', 'Other'")
    (geo / "districts_2022.geojson").write_text(json.dumps({"features": [{"properties": {"leaid": "1"}}]}), encoding="utf-8")
    assert derived.build_districts_index(tmp_path) == 2
    items = json.loads((geo / "districts_index.json").read_text(encoding="utf-8"))["districts"]
    assert items == [["1", "New Name", [2022]], ["2", "Other", []]]


def test_outputs_are_deterministic(tmp_path):
    _fixture(tmp_path)
    derived.build_school_metrics(tmp_path)
    a = (tmp_path / "derived/school_profile.parquet").read_bytes()
    derived.build_school_metrics(tmp_path)
    assert (tmp_path / "derived/school_profile.parquet").read_bytes() == a
