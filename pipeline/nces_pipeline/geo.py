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
      FROM (SELECT * REPLACE (TRY_CAST(latitude AS DOUBLE) AS latitude, TRY_CAST(longitud AS DOUBLE) AS longitud) FROM {hd}) h LEFT JOIN enr ON enr.unitid = h.unitid AND enr.year = h.year""")
    years = [r[0] for r in con.execute("SELECT DISTINCT year FROM per_year ORDER BY 1").fetchall()]
    rows = con.execute("""
      SELECT unitid, list(year ORDER BY year), list(cyactive ORDER BY year), list(total ORDER BY year),
             arg_max(instnm, year), arg_max(city, year), arg_max(sector, year), arg_max(control, year),
             arg_max(iclevel, year), arg_max(locale, year), arg_max(hbcu, year), arg_max(webaddr, year),
             arg_max(lat, CASE WHEN lat IS NULL THEN -1 ELSE year END),
             arg_max(lon, CASE WHEN lat IS NULL THEN -1 ELSE year END)
      FROM per_year GROUP BY unitid ORDER BY unitid""").fetchall()
    from .geocode import addr_key

    gc = _geocode_lookup()
    addr = {r[0]: r[1:] for r in con.execute(f"""
      SELECT unitid, arg_max(addr, year), arg_max(city, year), arg_max(stabbr, year), arg_max(zip, year)
      FROM {hd} GROUP BY unitid""").fetchall()}
    inst = []
    for (uid, ys, act, tot, name, city, sector, control, level, locale, hbcu, web, lat, lon) in rows:
        src, approx = "ipeds", False
        if lat is None or lon is None:
            k = addr_key(*addr.get(uid, (None,) * 4))
            if not (k and k in gc):
                continue
            lat, lon, approx = gc[k][0], gc[k][1], gc[k][2]
            src = "geocode"
        inst.append({
            "id": uid, "name": name, "city": city, "lat": round(lat, 6), "lon": round(lon, 6),
            "coordSource": src, "approx": approx,
            "years": ys, "active": [1 if a == 1 else 0 for a in act], "enroll": tot,
            "sector": sector, "control": control, "level": level, "locale": locale, "hbcu": hbcu, "web": web,
        })
    info = _ipeds_dict_tables().get("hd", {"values": {}})["values"]
    labels = {k: {c: lab for c, lab in info.get(k.upper(), {}).items()} for k in ("sector", "control", "iclevel", "locale")}
    out = {"dataset": "college", "years": years, "labels": labels, "institutions": inst}
    p = DOCS_DATA / "geo" / "points_college.json"
    p.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return len(inst)


def _geocode_lookup() -> dict[str, tuple[float, float, bool]]:
    from .geocode import load_cache

    return {k: (v["lat"], v["lon"], v["match_type"] != "Exact") for k, v in load_cache().items() if v["matched"]}


def build_points_private() -> int:
    """docs/data/geo/points_private.json: private schools from the PSS surveys that carry names and IDs
    (2005-06 on). Coordinates come from the survey, else from the Census geocode cache (marked approximate
    unless an exact match)."""
    import yaml

    from .geocode import addr_key
    from .pss import VALUE_LABELS

    pss = DOCS_DATA / "pss" / "schools"
    con = duckdb.connect()
    gc = _geocode_lookup()
    rows = con.execute(f"""
      SELECT ppin, year, name, address, city, zip, lat, lon, enrollment_total, teachers_fte, level, typology, relig,
             ulocale, state_abbrev
      FROM read_parquet('{pss.as_posix()}/*.parquet', union_by_name=true)
      WHERE ppin IS NOT NULL AND name IS NOT NULL ORDER BY ppin, year""").fetchall()
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(r[0], []).append(r)
    schools = []
    for ppin, rs in by.items():
        latest = rs[-1]
        lat = lon = None
        src, approx = "pss", False
        for r in reversed(rs):  # newest source coordinates first
            if r[6] is not None and r[7] is not None and r[6] != 0:
                lat, lon = r[6], r[7]
                break
        if lat is None:
            for r in reversed(rs):
                k = addr_key(r[3], r[4], r[14], r[5])
                if k and k in gc:
                    lat, lon, approx = gc[k][0], gc[k][1], gc[k][2]
                    src = "geocode"
                    break
        if lat is None:
            continue
        schools.append({
            "id": ppin, "name": latest[2], "address": latest[3], "city": latest[4], "zip": latest[5],
            "lat": round(lat, 6), "lon": round(lon, 6), "coordSource": src, "approx": approx,
            "years": [r[1] for r in rs], "enroll": [r[8] for r in rs], "teachers": [r[9] for r in rs],
            "level": latest[10], "typology": latest[11], "relig": latest[12], "ulocale": latest[13],
        })
    vl = (yaml.safe_load(VALUE_LABELS.read_text(encoding="utf-8")) or {}).get("values", {})
    labels = {k.lower(): vl.get(k, {}) for k in ("LEVEL", "TYPOLOGY", "RELIG")}
    years = sorted({y for sc in schools for y in sc["years"]})
    out = {"dataset": "private", "years": years, "labels": labels, "schools": schools}
    p = DOCS_DATA / "geo" / "points_private.json"
    p.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return len(schools)
