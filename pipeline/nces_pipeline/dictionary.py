"""Build docs/data/meta/dictionary.parquet.

Sources, in order of preference for a column's description:
  1. the newest NCES companion/layout workbook for the topic (column description by raw name),
  2. generic descriptions for columns this pipeline adds (year, flags, provenance),
  3. a humanized column name.
Caveats come from config/caveats.yml.
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import yaml

from .catalog import build_catalog, year_of
from .ccd_topics import TOPICS
from .config import CONFIG_DIR, DATA_RAW, DOCS_DATA, SCHEMAS
from .fetch import client, download
from .parquet import write_parquet

LEVEL = {"sch": "School", "lea": "District"}
COMP_NAME = {"directory": "Directory", "membership": "Membership", "staff": "Staff",
             "lunch": "Lunch Program Eligibility", "characteristics": "School Characteristics",
             "idea": "Children with Disabilities", "el": "English Learners"}

GENERIC = {
    "year": ("Year", "Fall year of the school year (2024 means 2024-25).", "year"),
    "school_year": ("School year", "School year label such as 2024-25.", "text"),
    "data_version": ("Data version", "Release status of the source file as labelled by NCES: preliminary (0a), provisional (1a) or final (2a).", "text"),
    "source_file": ("Source file", "Name of the NCES file this row was built from.", "text"),
    "value_flag": ("Value flag", "Why the value is what it is: reported, derived, adjusted, missing, not_applicable, not_reported, suppressed, not_meeting_standards or unknown_other. Missing/suppressed values are NULL, never 0.", "category"),
    "coord_source": ("Coordinate source", "Where lat/lon came from: edge (NCES EDGE), edge_prior_year (carried forward from an earlier EDGE year) or geocode (US Census Geocoder).", "category"),
    "coord_approximate": ("Approximate location", "True when the location is an approximate geocode match rather than a source-provided point.", "boolean"),
    "lat": ("Latitude", "Latitude in decimal degrees (WGS84/NAD83).", "degrees"),
    "lon": ("Longitude", "Longitude in decimal degrees (WGS84/NAD83).", "degrees"),
    "student_count": ("Student count", "Number of students in the category on the membership count date.", "students"),
    "teachers": ("Teachers (FTE)", "Full-time-equivalent teachers.", "FTE"),
    "staff_count": ("Staff (FTE)", "Full-time-equivalent staff in the category.", "FTE"),
}


EDGE_DESC = {
    "ncessch": ("School ID", "12-digit NCES school identifier (leaid + school number)."),
    "leaid": ("District ID", "7-digit NCES local education agency identifier."),
    "locale": ("Locale code", "NCES urban-centric locale code (11-13 city, 21-23 suburb, 31-33 town, 41-43 rural, by size/proximity)."),
    "county_fips": ("County FIPS", "5-digit county FIPS code of the school location."),
    "county_name": ("County", "County name."),
    "cbsa": ("CBSA code", "Core Based Statistical Area code."),
    "cbsa_name": ("CBSA name", "Core Based Statistical Area name."),
    "cbsa_type": ("CBSA type", "1 = metropolitan, 2 = micropolitan statistical area."),
    "csa": ("CSA code", "Combined Statistical Area code."),
    "csa_name": ("CSA name", "Combined Statistical Area name."),
    "necta": ("NECTA code", "New England City and Town Area code."),
    "necta_name": ("NECTA name", "New England City and Town Area name."),
    "metmic": ("Metro/micro status", "Metropolitan/micropolitan statistical area indicator (older files)."),
    "cd": ("Congressional district", "Congressional district code at the time of the file."),
    "sldl": ("State legislative district (lower)", "State legislative district, lower chamber."),
    "sldu": ("State legislative district (upper)", "State legislative district, upper chamber."),
    "street": ("Street", "Location street address."), "city": ("City", "Location city."),
    "state": ("State", "Location state abbreviation."), "zip": ("ZIP", "Location ZIP code."), "zip4": ("ZIP+4", "ZIP+4 extension."),
    "fipst": ("State FIPS", "State FIPS code."), "opstfips": ("Operating state FIPS", "FIPS of the state operating the school."),
    "school_name": ("School name", "School name as in the EDGE file."),
}


def humanize(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("_", " ")).strip().capitalize()


def _layout_descriptions(xlsx: Path) -> dict[str, tuple[str, str]]:
    con = duckdb.connect()
    con.execute("INSTALL excel; LOAD excel;")
    try:
        rows = con.execute(
            f"SELECT * FROM read_xlsx('{xlsx.as_posix()}', sheet='File Layout', all_varchar=true, header=false)"
        ).fetchall()
    except duckdb.Error:
        return {}
    # columns: 0 new-field, 1 variable name, 2 changes, 3 type, 4 length, 5 position, 6 description, 7 categorical values
    out = {}
    for r in rows[1:]:
        if r[1]:
            d = (r[6] or "").strip()
            cats = (r[7] or "").strip() if len(r) > 7 else ""
            out[r[1].strip()] = (d + (f" Values: {cats}" if cats else ""), (r[3] or "").strip())
    return out


def _companion_for(level: str, comp: str, cat: list[dict]) -> Path | None:
    best = None
    for f in cat:
        if (f["elementType"] == "Documentation" and f["level"] == LEVEL[level]
                and (f["component"] or "").strip() == COMP_NAME[comp] and f["fileURL"].lower().endswith(".xlsx")
                and "companion" in f["fileURL"].lower()):
            y = year_of(f["schoolYear"])
            if best is None or y > best[0]:
                best = (y, f["fileURL"])
    if not best:
        return None
    url = best[1] if best[1].startswith("http") else "https://nces.ed.gov/ccd/" + best[1].lstrip("/")
    return download(url, f"ccd/docs/{url.rsplit('/', 1)[-1]}", source="ccd-doc", release=str(best[0]))


def _table_columns(dataset: str, table: str) -> dict[str, dict]:
    """canonical column -> {raw: {year: raw_name}, years: [..], type}"""
    out: dict[str, dict] = {}
    for p in sorted((SCHEMAS / dataset / table).glob("*.yml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        y = d["year"]
        for raw, spec in d["columns"].items():
            if spec.get("ignore") or spec.get("unpivot"):
                continue
            e = out.setdefault(spec["name"], {"raw": {}, "years": [], "type": spec.get("type", "VARCHAR")})
            e["raw"][y] = raw
            e["years"].append(y)
        for u in d.get("unpivot") or []:
            for k in u:
                if k != "source":
                    out.setdefault(k, {"raw": {}, "years": [], "type": "VARCHAR"})["years"].append(y)
        t = TOPICS.get(table)
        if t and t.kind == "long":
            for k in (t.value, "value_flag"):
                e = out.setdefault(k, {"raw": {}, "years": [], "type": t.value_type})
                e["years"].append(y)
    return out


def _parquet_presence(table_dir: Path) -> dict[str, list[int]]:
    """column -> years in which the column has at least one non-NULL value."""
    con = duckdb.connect()
    out: dict[str, list[int]] = {}
    order: list[str] = []
    for f in sorted(table_dir.glob("*.parquet")):
        y = int(f.stem)
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{f.as_posix()}')").fetchall()]
        counts = con.execute(
            "SELECT " + ", ".join(f'count("{c}")' for c in cols) + f" FROM read_parquet('{f.as_posix()}')"
        ).fetchone()
        for c, n in zip(cols, counts):
            if c not in out:
                out[c] = []
                order.append(c)
            if n:
                out[c].append(y)
    return {c: out[c] for c in order}


CAVEAT_COLUMNS = {"value_flag", "student_count", "teachers", "staff_count", "status", "lat", "lon", "coord_source"}


def build_dictionary() -> int:
    caveats = yaml.safe_load((CONFIG_DIR / "caveats.yml").read_text(encoding="utf-8")) or {}
    cat = build_catalog()
    rows = []
    for table_dir in sorted(p for p in (DOCS_DATA / "ccd").iterdir() if p.is_dir()):
        table = table_dir.name
        t = TOPICS.get(table)
        desc: dict[str, tuple[str, str]] = {}
        if t:
            lvl, comp = t.component.split("_", 1)
            doc = _companion_for(lvl, comp, cat)
            if doc:
                desc = _layout_descriptions(doc)
        maps = _table_columns("ccd" if t else "edge", table)
        table_cav = (caveats.get(f"ccd.{table}") or {}).get("caveat", "")
        for name, years in _parquet_presence(table_dir).items():
            label, description, unit = GENERIC.get(name, (humanize(name), "", ""))
            if table == "school_location" and name in EDGE_DESC:
                label, description = EDGE_DESC[name]
            base = name[:-5] if name.endswith("_flag") and name not in GENERIC else None
            if base:
                label, description, unit = (humanize(base) + " flag",
                                            f"Why {base} has the value it has (reported, missing, not_applicable, suppressed...). NULL value with a flag is never a zero.", "category")
            elif name not in GENERIC and name in maps:
                for y in sorted(maps[name]["raw"], reverse=True):
                    rn = maps[name]["raw"][y]
                    if rn in desc and desc[rn][0]:
                        description = desc[rn][0]
                        break
            col_cav = (caveats.get(f"ccd.{table}.{name}") or {}).get("caveat", "")
            caveat = col_cav or (table_cav if name in CAVEAT_COLUMNS or base else "")
            yrs = years or [int(f.stem) for f in table_dir.glob("*.parquet")]
            rows.append(("ccd", table, name, label, description, unit, min(yrs), max(yrs), caveat))
    con = duckdb.connect()
    con.execute('CREATE TABLE d(dataset VARCHAR, "table" VARCHAR, "column" VARCHAR, label VARCHAR, description VARCHAR, unit VARCHAR, first_year INTEGER, last_year INTEGER, caveat VARCHAR)')
    con.executemany("INSERT INTO d VALUES (?,?,?,?,?,?,?,?,?)", rows)
    return write_parquet(con, "SELECT * FROM d", DOCS_DATA / "meta" / "dictionary.parquet",
                         ["dataset", '"table"', '"column"'])
