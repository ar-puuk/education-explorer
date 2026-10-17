"""Derived outputs the web app reads directly (so the browser does less work):

  derived/school_metrics/<year>.parquet  one row per school-year: enrollment, teachers, students per teacher, lunch share
  derived/school_profile.parquet         one row per school with those series as arrays (one read per inspector)
  meta/year_summary.json                 places per year per dataset (timeline histogram, no Parquet scan)
  meta/state_reference.json              median and quartiles per metric per year across operating public schools
  geo/districts_index.json               district names for search (all districts ever in the directory, with boundary years)

Everything is computed from the committed tables, so it is state independent and deterministic. Metrics are descriptive:
nothing here ranks schools or implies quality.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from .config import DOCS_DATA
from .parquet import write_parquet

NON_OPERATING = ("Closed", "Future", "Future School")
MIN_N = 10  # a reference band needs at least this many schools in a year
MAX_FRL_SHARE = 1.5  # larger shares are data errors (counts above enrollment), left out of the reference band
METRICS = {
    "enrollment": "School enrollment",
    "students_per_teacher": "Students per teacher (FTE)",
    "frl_share": "Free or reduced-price lunch eligible, share of enrollment",
}


def _pq(base: Path, rel: str) -> str:
    return f"read_parquet('{(base / rel).as_posix()}/*.parquet', union_by_name=true)"


def _write_json(path: Path, doc: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, separators=(",", ":"), ensure_ascii=False, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- school metrics + profile
def build_school_metrics(base: Path = DOCS_DATA) -> int:
    """derived/school_metrics/<year>.parquet and derived/school_profile.parquet. Returns the school-year row count."""
    ccd = base / "ccd"
    if not (ccd / "school_directory").exists() or not (ccd / "membership").exists():
        return 0
    con = duckdb.connect()
    has_staff = (ccd / "staff").exists()
    has_lunch = (ccd / "lunch").exists()
    staff = (
        f"SELECT ncessch, year, max(teachers) AS teachers_fte FROM {_pq(base, 'ccd/staff')} "
        "WHERE total_indicator = 'Education Unit Total' GROUP BY 1, 2"
        if has_staff else "SELECT NULL::VARCHAR ncessch, NULL::INTEGER year, NULL::DOUBLE teachers_fte WHERE false"
    )
    lunch = (
        f"SELECT ncessch, year, "
        "max(student_count) FILTER (WHERE data_group = 'Free and Reduced-price Lunch Table' AND total_indicator = 'Category Set A' "
        "AND lunch_program = 'Free lunch qualified') AS free, "
        "max(student_count) FILTER (WHERE data_group = 'Free and Reduced-price Lunch Table' AND total_indicator = 'Category Set A' "
        f"AND lunch_program = 'Reduced-price lunch qualified') AS reduced FROM {_pq(base, 'ccd/lunch')} GROUP BY 1, 2"
        if has_lunch else "SELECT NULL::VARCHAR ncessch, NULL::INTEGER year, NULL::INTEGER free, NULL::INTEGER reduced WHERE false"
    )
    con.execute(f"""
      CREATE TABLE sm AS
      WITH enr AS (SELECT ncessch, year, max(student_count) AS enrollment FROM {_pq(base, 'ccd/membership')}
                   WHERE total_indicator = 'Education Unit Total' GROUP BY 1, 2),
           tch AS ({staff}), frl AS ({lunch})
      SELECT d.year, d.ncessch, d.leaid, d.status, d.level,
             enr.enrollment, tch.teachers_fte,
             CASE WHEN enr.enrollment IS NOT NULL AND tch.teachers_fte > 0
                  THEN round(enr.enrollment / tch.teachers_fte, 1) END AS students_per_teacher,
             CASE WHEN frl.free IS NOT NULL AND frl.reduced IS NOT NULL THEN frl.free + frl.reduced END AS frl_count,
             CASE WHEN frl.free IS NOT NULL AND frl.reduced IS NOT NULL AND enr.enrollment > 0
                  THEN round((frl.free + frl.reduced) / enr.enrollment::DOUBLE, 4) END AS frl_share
      FROM {_pq(base, 'ccd/school_directory')} d
      LEFT JOIN enr ON enr.ncessch = d.ncessch AND enr.year = d.year
      LEFT JOIN tch ON tch.ncessch = d.ncessch AND tch.year = d.year
      LEFT JOIN frl ON frl.ncessch = d.ncessch AND frl.year = d.year""")
    out = base / "derived" / "school_metrics"
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.parquet"):
        stale.unlink()
    total = 0
    for (y,) in con.execute("SELECT DISTINCT year FROM sm ORDER BY 1").fetchall():
        total += write_parquet(con, f"SELECT * FROM sm WHERE year = {int(y)}", out / f"{int(y)}.parquet", ["ncessch"])
    write_parquet(con, """
      SELECT ncessch,
             list(year ORDER BY year) AS years,
             list(enrollment ORDER BY year) AS enrollment,
             list(teachers_fte ORDER BY year) AS teachers_fte,
             list(students_per_teacher ORDER BY year) AS students_per_teacher,
             list(frl_share ORDER BY year) AS frl_share
      FROM sm GROUP BY ncessch""", base / "derived" / "school_profile.parquet", ["ncessch"])
    return total


# ---------------------------------------------------------------- state reference bands
def build_state_reference(base: Path = DOCS_DATA) -> dict:
    """meta/state_reference.json: per metric and year, n and the quartiles over operating public schools."""
    out: dict = {"scope": "operating public schools in the state, all levels", "min_n": MIN_N, "metrics": {}}
    src = base / "derived" / "school_metrics"
    if src.exists():
        con = duckdb.connect()
        non_op = ", ".join(f"'{s}'" for s in NON_OPERATING)
        view = f"read_parquet('{src.as_posix()}/*.parquet')"
        for col, label in METRICS.items():
            extra = f" AND {col} <= {MAX_FRL_SHARE}" if col == "frl_share" else ""
            rows = con.execute(f"""
              SELECT year, count(*), quantile_cont({col}, 0.25), quantile_cont({col}, 0.5), quantile_cont({col}, 0.75)
              FROM {view}
              WHERE {col} IS NOT NULL AND {col} > 0 AND coalesce(status, '') NOT IN ({non_op}){extra}
              GROUP BY 1 HAVING count(*) >= {MIN_N} ORDER BY 1""").fetchall()
            ndig = 4 if col == "frl_share" else 1
            out["metrics"][col] = {
                "label": label,
                "years": {str(y): {"n": n, "p25": round(a, ndig), "median": round(m, ndig), "p75": round(b, ndig)} for y, n, a, m, b in rows},
            }
    _write_json(base / "meta" / "state_reference.json", out)
    return out


# ---------------------------------------------------------------- year summary
def build_year_summary(base: Path = DOCS_DATA) -> dict:
    """meta/year_summary.json from the points files (what the map can show) and the school directory."""
    out: dict = {"public": {}, "private": {}, "college": {}, "private_survey_years": []}
    geo = base / "geo"

    def load(name: str) -> dict | None:
        p = geo / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    pub = load("points_public.json")
    if pub:
        status = pub["statuses"]
        non_op = {i for i, s in enumerate(status) if s in NON_OPERATING}
        mapped: dict[int, int] = {}
        operating: dict[int, int] = {}
        for s in pub["schools"]:
            for y, st in zip(s["years"], s["status"]):
                mapped[y] = mapped.get(y, 0) + 1
                if st not in non_op:
                    operating[y] = operating.get(y, 0) + 1
        con = duckdb.connect()
        d = base / "ccd" / "school_directory"
        directory = (
            dict(con.execute(f"SELECT year, count(*) FROM {_pq(base, 'ccd/school_directory')} GROUP BY 1").fetchall())
            if d.exists() else {}
        )
        out["public"] = {str(y): {"mapped": mapped[y], "operating": operating.get(y, 0), "directory": directory.get(y)} for y in sorted(mapped)}
    col = load("points_college.json")
    if col:
        n: dict[int, int] = {}
        act: dict[int, int] = {}
        for s in col["institutions"]:
            for y, a in zip(s["years"], s["active"]):
                n[y] = n.get(y, 0) + 1
                act[y] = act.get(y, 0) + (1 if a == 1 else 0)
        out["college"] = {str(y): {"mapped": n[y], "active": act[y]} for y in sorted(n)}
    prv = load("points_private.json")
    if prv:
        n = {}
        for s in prv["schools"]:
            for y in s["years"]:
                n[y] = n.get(y, 0) + 1
        out["private"] = {str(y): {"mapped": n[y]} for y in sorted(n)}
        out["private_survey_years"] = sorted(prv["years"])
    _write_json(base / "meta" / "year_summary.json", out)
    return out


# ---------------------------------------------------------------- district search index
def build_districts_index(base: Path = DOCS_DATA) -> int:
    """geo/districts_index.json: [leaid, name, [boundary years]] for every district ever in the directory."""
    d = base / "ccd" / "district_directory"
    if not d.exists():
        return 0
    con = duckdb.connect()
    rows = con.execute(
        f"SELECT leaid, arg_max(lea_name, year) FROM {_pq(base, 'ccd/district_directory')} "
        "WHERE leaid IS NOT NULL GROUP BY 1 ORDER BY 1"
    ).fetchall()
    bound: dict[str, list[int]] = {}
    for gj in sorted((base / "geo").glob("districts_*.geojson")):
        year = int(gj.stem.split("_")[1])
        for f in json.loads(gj.read_text(encoding="utf-8"))["features"]:
            bound.setdefault(str(f["properties"]["leaid"]), []).append(year)
    items = [[leaid, name or leaid, bound.get(leaid, [])] for leaid, name in rows]
    _write_json(base / "geo" / "districts_index.json", {"districts": items})
    return len(items)


def build_derived(base: Path = DOCS_DATA) -> dict:
    n = build_school_metrics(base)
    ref = build_state_reference(base)
    summary = build_year_summary(base)
    nd = build_districts_index(base)
    return {"school_metric_rows": n, "reference_metrics": len(ref["metrics"]), "years": len(summary["public"]), "districts": nd}
