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


def build_points_college() -> int:
    """docs/data/geo/points_college.json: every institution that appears in any year's IPEDS directory
    and has coordinates, with per-year presence/active status and fall enrollment (all students)."""
    from .dictionary import _ipeds_dict_tables

    ipeds = DOCS_DATA / "ipeds"
    con = duckdb.connect()
    hd = f"read_parquet('{(ipeds / 'hd').as_posix()}/*.parquet', union_by_name=true)"
    efa = f"read_parquet('{(ipeds / 'efa').as_posix()}/*.parquet', union_by_name=true)"
    con.execute(f"""
      CREATE TABLE enr AS
      SELECT unitid, year, max(eftotlt) AS total FROM {efa} WHERE efalevel = 1 GROUP BY 1, 2""")
    con.execute(f"""
      CREATE TABLE per_year AS
      SELECT h.unitid, h.year, h.instnm, h.city, h.stabbr, h.sector, h.control, h.iclevel, h.locale, h.hbcu,
             h.cyactive, h.webaddr,
             CASE WHEN h.latitude BETWEEN -90 AND 90 AND h.longitud BETWEEN -180 AND 180
                       AND h.latitude <> 0 AND h.longitud <> 0 THEN h.latitude END AS lat,
             CASE WHEN h.latitude BETWEEN -90 AND 90 AND h.longitud BETWEEN -180 AND 180
                       AND h.latitude <> 0 AND h.longitud <> 0 THEN h.longitud END AS lon,
             enr.total
      FROM {hd} h LEFT JOIN enr ON enr.unitid = h.unitid AND enr.year = h.year""")
    years = [r[0] for r in con.execute("SELECT DISTINCT year FROM per_year ORDER BY 1").fetchall()]
    rows = con.execute("""
      SELECT unitid, list(year ORDER BY year), list(cyactive ORDER BY year), list(total ORDER BY year),
             arg_max(instnm, year), arg_max(city, year), arg_max(sector, year), arg_max(control, year),
             arg_max(iclevel, year), arg_max(locale, year), arg_max(hbcu, year), arg_max(webaddr, year),
             arg_max(lat, CASE WHEN lat IS NULL THEN -1 ELSE year END),
             arg_max(lon, CASE WHEN lat IS NULL THEN -1 ELSE year END)
      FROM per_year GROUP BY unitid ORDER BY unitid""").fetchall()
    inst = []
    for (uid, ys, act, tot, name, city, sector, control, level, locale, hbcu, web, lat, lon) in rows:
        if lat is None or lon is None:
            continue
        inst.append({
            "id": uid, "name": name, "city": city, "lat": round(lat, 6), "lon": round(lon, 6),
            "years": ys, "active": [1 if a == 1 else 0 for a in act], "enroll": tot,
            "sector": sector, "control": control, "level": level, "locale": locale, "hbcu": hbcu, "web": web,
        })
    info = _ipeds_dict_tables().get("hd", {"values": {}})["values"]
    labels = {k: {c: lab for c, lab in info.get(k.upper(), {}).items()} for k in ("sector", "control", "iclevel", "locale")}
    out = {"dataset": "college", "years": years, "labels": labels, "institutions": inst}
    p = DOCS_DATA / "geo" / "points_college.json"
    p.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return len(inst)
