"""US Census batch geocoder with a committed cache.

Only addresses that lack trustworthy source coordinates are sent. Results (including no-matches) are cached in
docs/data/meta/geocode_cache.parquet keyed by a normalized address, so reruns never re-geocode.
"""
from __future__ import annotations

import csv
import io
import re
import time
from datetime import date
from pathlib import Path

import duckdb
import httpx

from .config import DOCS_DATA, State, load_sources
from .fetch import UA
from .parquet import write_parquet

CACHE = DOCS_DATA / "meta" / "geocode_cache.parquet"
REPORT = Path(__file__).resolve().parents[2] / "data-raw" / "geocode_report.txt"  # not committed (data-raw/*)


def addr_key(street: str | None, city: str | None, state: str | None, zip_: str | None) -> str | None:
    """Normalized key: upper case, punctuation stripped, ZIP5 only. None when there is no usable street."""
    def n(x: str | None) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 /#-]", " ", (x or "").upper())).strip()

    st = n(street)
    if not st or re.match(r"^(P ?O ?BOX|POB|BOX) ", st):  # PO boxes cannot be located
        return None
    z = re.sub(r"\D", "", zip_ or "")[:5]
    return f"{st}|{n(city)}|{n(state)}|{z}"


def input_address(key: str) -> str:
    st, city, state, z = key.split("|")
    return f"{st}, {city}, {state} {z}".strip()


def load_cache() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    con = duckdb.connect()
    rows = con.execute(f"SELECT * FROM read_parquet('{CACHE.as_posix()}')").fetchall()
    cols = [d[0] for d in con.description]
    return {r[0]: dict(zip(cols, r)) for r in rows}


def save_cache(cache: dict[str, dict]) -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE c(addr_key VARCHAR, input_address VARCHAR, matched BOOLEAN, match_type VARCHAR, "
                "lat DOUBLE, lon DOUBLE, tiger_line_id VARCHAR, benchmark VARCHAR, geocoded_on VARCHAR)")
    con.executemany("INSERT INTO c VALUES (?,?,?,?,?,?,?,?,?)",
                    [(k, v["input_address"], v["matched"], v["match_type"], v["lat"], v["lon"], v["tiger_line_id"],
                      v["benchmark"], v["geocoded_on"]) for k, v in cache.items()])
    write_parquet(con, "SELECT * FROM c", CACHE, ["addr_key"])


def pending_addresses(state: State) -> dict[str, list[str]]:
    """addr_key -> sources, for addresses that need geocoding (no source coordinates)."""
    con = duckdb.connect()
    out: dict[str, list[str]] = {}

    def add(rows, source):
        for street, city, st, z in rows:
            k = addr_key(street, city, st, z)
            if k:
                out.setdefault(k, []).append(source)

    ccd = DOCS_DATA / "ccd"
    if (ccd / "school_directory").exists() and (ccd / "school_location").exists():
        add(con.execute(f"""
          SELECT d.street1, d.city, d.state, d.zip
          FROM read_parquet('{(ccd / 'school_directory').as_posix()}/*.parquet', union_by_name=true) d
          LEFT JOIN read_parquet('{(ccd / 'school_location').as_posix()}/*.parquet', union_by_name=true) l
            ON l.ncessch = d.ncessch AND l.year = d.year
          WHERE l.lat IS NULL""").fetchall(), "ccd")
    pss = DOCS_DATA / "pss" / "schools"
    if pss.exists():
        add(con.execute(f"""
          SELECT address, city, state_abbrev, zip FROM read_parquet('{pss.as_posix()}/*.parquet', union_by_name=true)
          WHERE name IS NOT NULL AND (lat IS NULL OR lon IS NULL OR lat = 0)""").fetchall(), "pss")
    hd = DOCS_DATA / "ipeds" / "hd"
    if hd.exists():
        add(con.execute(f"""
          SELECT addr, city, stabbr, zip FROM read_parquet('{hd.as_posix()}/*.parquet', union_by_name=true)
          WHERE TRY_CAST(latitude AS DOUBLE) IS NULL OR TRY_CAST(longitud AS DOUBLE) IS NULL OR TRY_CAST(latitude AS DOUBLE) = 0""").fetchall(), "ipeds")
    return out


def _post(client: httpx.Client, url: str, benchmark: str, lines: list[tuple[int, str, str, str, str]]) -> list[list[str]]:
    buf = io.StringIO()
    w = csv.writer(buf)
    for row in lines:
        w.writerow(row)
    for attempt in range(5):
        try:
            r = client.post(url, data={"benchmark": benchmark, "returntype": "locations"},
                            files={"addressFile": ("addresses.csv", buf.getvalue().encode("utf-8"), "text/csv")})
            r.raise_for_status()
            return list(csv.reader(io.StringIO(r.text)))
        except httpx.HTTPError:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    return []


def geocode_pending(state: State, limit: int | None = None) -> dict[str, int]:
    cfg = load_sources()["census_geocoder"]
    cache = load_cache()
    todo = [k for k in pending_addresses(state) if k not in cache]
    if limit:
        todo = todo[:limit]
    stats = {"pending": len(todo), "matched": 0, "no_match": 0}
    if not todo:
        return stats
    size = int(cfg.get("batch_size", 2000))
    today = date.today().isoformat()
    with httpx.Client(headers=UA, timeout=httpx.Timeout(60, read=600)) as c:
        for i in range(0, len(todo), size):
            chunk = todo[i:i + size]
            lines = []
            for j, k in enumerate(chunk):
                st, city, s, z = k.split("|")
                lines.append((j, st, city, s, z))
            for row in _post(c, cfg["url"], cfg["benchmark"], lines):
                if len(row) < 3:
                    continue
                k = chunk[int(row[0])]
                ok = row[2] == "Match" and len(row) > 5 and row[5]
                lon, lat = (float(x) for x in row[5].split(",")) if ok else (None, None)
                cache[k] = {"input_address": input_address(k), "matched": bool(ok),
                            "match_type": row[3] if ok and len(row) > 3 else ("Tie" if row[2] == "Tie" else "No_Match"),
                            "lat": lat, "lon": lon, "tiger_line_id": row[6] if ok and len(row) > 6 else None,
                            "benchmark": cfg["benchmark"], "geocoded_on": today}
                stats["matched" if ok else "no_match"] += 1
            save_cache(cache)  # resume-safe: persisted after every batch
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(f"{v['input_address']}\t{v['match_type']}" for v in cache.values() if not v["matched"]) + "\n",
                      encoding="utf-8", newline="\n")
    return stats


def apply_to_ccd_locations() -> int:
    """Add school_location rows (coord_source='geocode') for directory school-years that have no location."""
    cache = {k: v for k, v in load_cache().items() if v["matched"]}
    if not cache:
        return 0
    ccd = DOCS_DATA / "ccd"
    con = duckdb.connect()
    con.execute("CREATE TABLE g(addr_key VARCHAR, lat DOUBLE, lon DOUBLE, approx BOOLEAN)")
    con.executemany("INSERT INTO g VALUES (?,?,?,?)", [(k, v["lat"], v["lon"], v["match_type"] != "Exact") for k, v in cache.items()])
    n = 0
    for dp in sorted((ccd / "school_directory").glob("*.parquet")):
        y = int(dp.stem)
        lp = ccd / "school_location" / f"{y}.parquet"
        if not lp.exists():
            continue
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{lp.as_posix()}')").fetchall()]
        rows = con.execute(f"SELECT d.ncessch, d.leaid, d.school_name, d.street1, d.city, d.state, d.zip, d.fipst "
                           f"FROM read_parquet('{dp.as_posix()}') d WHERE NOT EXISTS "
                           f"(SELECT 1 FROM read_parquet('{lp.as_posix()}') l WHERE l.ncessch = d.ncessch AND l.lat IS NOT NULL)").fetchall()
        add = []
        for ncessch, leaid, name, street, city, st, z, fipst in rows:
            k = addr_key(street, city, st, z)
            if k and k in cache:
                add.append((ncessch, leaid, name, street, city, st, z, fipst, cache[k]["lat"], cache[k]["lon"],
                            cache[k]["match_type"] != "Exact"))
        # rebuild the year file: existing rows (filled in where lat is missing) + rows for schools with no location row
        con.execute("DROP TABLE IF EXISTS add_rows")
        con.execute("CREATE TABLE add_rows(ncessch VARCHAR, leaid VARCHAR, school_name VARCHAR, street VARCHAR, city VARCHAR, "
                    "state VARCHAR, zip VARCHAR, fipst VARCHAR, lat DOUBLE, lon DOUBLE, approx BOOLEAN)")
        if add:
            con.executemany("INSERT INTO add_rows VALUES (?,?,?,?,?,?,?,?,?,?,?)", add)
        new_cols = ", ".join(
            {"ncessch": "a.ncessch", "leaid": "a.leaid", "school_name": "a.school_name", "street": "a.street", "city": "a.city",
             "state": "a.state", "zip": "a.zip", "fipst": "a.fipst", "lat": "a.lat", "lon": "a.lon",
             "coord_source": "'geocode'", "coord_approximate": "a.approx",
             "year": str(y), "school_year": f"'{y}-{(y + 1) % 100:02d}'",
             "source_file": "'census_geocoder'"}.get(c, "NULL") + f' AS "{c}"' for c in cols)
        sql = f"""
          SELECT l.* REPLACE (
              coalesce(l.lat, a.lat) AS lat, coalesce(l.lon, a.lon) AS lon,
              CASE WHEN l.lat IS NULL AND a.lat IS NOT NULL THEN 'geocode' ELSE l.coord_source END AS coord_source,
              CASE WHEN l.lat IS NULL AND a.lat IS NOT NULL THEN a.approx ELSE l.coord_approximate END AS coord_approximate)
          FROM read_parquet('{lp.as_posix()}') l LEFT JOIN add_rows a ON a.ncessch = l.ncessch
          UNION ALL
          SELECT {new_cols} FROM add_rows a WHERE NOT EXISTS
            (SELECT 1 FROM read_parquet('{lp.as_posix()}') l WHERE l.ncessch = a.ncessch)"""
        tmp = lp.with_suffix(".src.parquet")
        con.execute(f"COPY ({sql}) TO '{tmp.as_posix()}' (FORMAT PARQUET)")
        write_parquet(con, f"SELECT * FROM read_parquet('{tmp.as_posix()}')", lp, ["ncessch"])
        tmp.unlink()
        n += len(add)
    return n
