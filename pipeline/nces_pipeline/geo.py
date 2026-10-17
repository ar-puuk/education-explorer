"""Small prebuilt files for first paint: one points file per dataset."""
from __future__ import annotations

import json

import duckdb

from .config import DOCS_DATA


def build_points_public() -> int:
    """docs/data/geo/points_public.json: every school that ever appears in the CCD directory and has
    coordinates in some year, with per-year presence, status and total enrollment arrays."""
    ccd = DOCS_DATA / "ccd"
    con = duckdb.connect()
    d = f"read_parquet('{(ccd / 'school_directory').as_posix()}/*.parquet', union_by_name=true)"
    l = f"read_parquet('{(ccd / 'school_location').as_posix()}/*.parquet', union_by_name=true)"
    m = f"read_parquet('{(ccd / 'membership').as_posix()}/*.parquet', union_by_name=true)"
    con.execute(f"""
      CREATE TABLE enr AS
      SELECT ncessch, year, max(student_count) AS total FROM {m}
      WHERE total_indicator = 'Education Unit Total' GROUP BY 1, 2""")
    con.execute(f"""
      CREATE TABLE per_year AS
      SELECT d.ncessch, d.year, d.school_name, d.leaid, d.lea_name, d.status, d.level, d.charter,
             d.school_type, d.grade_low, d.grade_high,
             loc.lat, loc.lon, loc.locale, loc.county_name, loc.coord_source,
             enr.total
      FROM {d} d
      LEFT JOIN {l} loc ON loc.ncessch = d.ncessch AND loc.year = d.year
      LEFT JOIN enr ON enr.ncessch = d.ncessch AND enr.year = d.year""")
    years = [r[0] for r in con.execute("SELECT DISTINCT year FROM per_year ORDER BY 1").fetchall()]
    statuses = [r[0] for r in con.execute("SELECT DISTINCT status FROM per_year WHERE status IS NOT NULL ORDER BY 1").fetchall()]
    sidx = {s: i for i, s in enumerate(statuses)}
    rows = con.execute("""
      SELECT ncessch, list(year ORDER BY year), list(status ORDER BY year), list(total ORDER BY year),
             arg_max(school_name, year), arg_max(leaid, year), arg_max(lea_name, year), arg_max(level, year),
             arg_max(charter, year), arg_max(school_type, year), arg_max(grade_low, year), arg_max(grade_high, year),
             arg_max(lat, CASE WHEN lat IS NULL THEN -1 ELSE year END),
             arg_max(lon, CASE WHEN lat IS NULL THEN -1 ELSE year END),
             arg_max(locale, CASE WHEN locale IS NULL THEN -1 ELSE year END),
             arg_max(county_name, CASE WHEN county_name IS NULL THEN -1 ELSE year END),
             arg_max(coord_source, CASE WHEN lat IS NULL THEN -1 ELSE year END)
      FROM per_year GROUP BY ncessch ORDER BY ncessch""").fetchall()
    schools = []
    for (nid, ys, sts, tot, name, leaid, lea, level, charter, stype, glo, ghi, lat, lon, locale, county, csrc) in rows:
        if lat is None or lon is None:
            continue
        schools.append({
            "id": nid, "name": name, "leaid": leaid, "lea": lea, "lat": round(lat, 6), "lon": round(lon, 6),
            "years": ys, "status": [sidx.get(s, -1) for s in sts], "enroll": tot,
            "level": level, "charter": charter, "type": stype, "gradeLow": glo, "gradeHigh": ghi,
            "locale": locale, "county": county, "coordSource": csrc,
        })
    out = {"dataset": "public", "years": years, "statuses": statuses, "schools": schools}
    p = DOCS_DATA / "geo" / "points_public.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return len(schools)
