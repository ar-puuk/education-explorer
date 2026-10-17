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
from .config import CONFIG_DIR, DOCS_DATA, SCHEMAS
from .fetch import download
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


ACRONYMS = {"nslp", "lea", "id", "ig", "bies", "cbsa", "csa", "necta", "cd", "sldl", "sldu", "zip", "fips", "idea", "el", "pk", "kg", "ug", "ae"}


def humanize(name: str) -> str:
    words = re.sub(r"\s+", " ", name.replace("_", " ")).strip().split(" ")
    words = [w.upper() if w in ACRONYMS else w for w in words]
    s = " ".join(words)
    return s[0].upper() + s[1:] if s else s


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
    irows, ivals = ipeds_dictionary_rows()
    prows, pvals = pss_dictionary_rows()
    rows += irows + prows
    ivals += pvals
    con = duckdb.connect()
    con.execute('CREATE TABLE d(dataset VARCHAR, "table" VARCHAR, "column" VARCHAR, label VARCHAR, description VARCHAR, unit VARCHAR, first_year INTEGER, last_year INTEGER, caveat VARCHAR)')
    con.executemany("INSERT INTO d VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.execute('CREATE TABLE v(dataset VARCHAR, "table" VARCHAR, "column" VARCHAR, code VARCHAR, label VARCHAR)')
    con.executemany("INSERT INTO v VALUES (?,?,?,?,?)", ivals)
    write_parquet(con, "SELECT * FROM v", DOCS_DATA / "meta" / "value_labels.parquet",
                  ["dataset", '"table"', '"column"', "code"])
    return write_parquet(con, "SELECT * FROM d", DOCS_DATA / "meta" / "dictionary.parquet",
                         ["dataset", '"table"', '"column"'])


# ------------------------------------------------------------------------------------ IPEDS
def _sheet_rows(con, x: Path, *names: str) -> list[tuple]:
    """Rows of the first sheet that exists under any of the given spellings (sheet names vary by year)."""
    for n in names:
        for variant in dict.fromkeys([n, n.lower(), n.capitalize(), n.upper()]):
            try:
                return con.execute(f"SELECT * FROM read_xlsx('{x.as_posix()}', sheet='{variant}', all_varchar=true)").fetchall()
            except duckdb.Error:
                continue
    return []


def _ipeds_dict_tables() -> dict[str, dict]:
    """family -> {'labels': {COL: title}, 'desc': {COL: long description}, 'values': {COL: {code: label}}}
    from the newest data dictionary that lists each column."""
    from .ipeds_build import years_from_str
    from .ipeds_files import dict_xlsx, select

    con = duckdb.connect()
    con.execute("INSTALL excel; LOAD excel;")
    fams: dict[str, dict] = {}
    for f in sorted(select(), key=lambda x: -x.year):
        x = dict_xlsx(f)
        if not x:
            continue
        e = fams.setdefault(f.family, {"labels": {}, "desc": {}, "values": {}, "title": {}, "survey": f.survey})
        e["title"].setdefault(f.year, f.title)
        for r in _sheet_rows(con, x, "Varlist"):
            if r[1]:
                e["labels"].setdefault(r[1].upper(), (r[6] or "").strip() if len(r) > 6 else "")
        for r in _sheet_rows(con, x, "Description"):
            if r[1] and len(r) > 2 and r[2]:
                e["desc"].setdefault(r[1].upper(), re.sub(r"_x000D_|" + chr(13), "", r[2]).strip())
        seen = set()
        for r in _sheet_rows(con, x, "Frequencies"):
            if r[0] and len(r) > 4 and r[3] is not None:
                col = r[0].upper()
                if col in e["values"] and col not in seen:
                    continue  # a newer year already supplied this column's labels
                seen.add(col)
                e["values"].setdefault(col, {}).setdefault(r[3], (r[4] or "").strip())
    _ = years_from_str
    return fams


def ipeds_dictionary_rows() -> tuple[list[tuple], list[tuple]]:
    """(dictionary rows, value-label rows) for every IPEDS table present in docs/data/ipeds."""
    from .ipeds_build import load_family_map, years_from_str

    caveats = yaml.safe_load((CONFIG_DIR / "caveats.yml").read_text(encoding="utf-8")) or {}
    fams = _ipeds_dict_tables()
    rows, vals = [], []
    base = DOCS_DATA / "ipeds"
    if not base.exists():
        return rows, vals
    for table_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        fam = table_dir.name
        info = fams.get(fam, {"labels": {}, "desc": {}, "values": {}})
        try:
            m = load_family_map(fam)
        except SystemExit:
            continue
        table_cav = (caveats.get(f"ipeds.{fam}") or {}).get("caveat", "")
        by_name = {spec["name"]: (raw, spec) for raw, spec in m["columns"].items()}
        presence = _parquet_presence(table_dir)
        for name, years in presence.items():
            if name in ("year", "data_version", "source_file"):
                label, description, unit = GENERIC.get(name, (humanize(name), "", ""))
                rows.append(("ipeds", fam, name, label, description, unit, min(years or [0]) or None, max(years or [0]) or None, ""))
                continue
            raw, spec = by_name.get(name, (name.upper(), {"years": ""}))
            yrs = sorted(years_from_str(spec.get("years", ""))) or [int(f.stem) for f in table_dir.glob("*.parquet")]
            flag_for = spec.get("flag_for")
            if flag_for:
                label = f"{info['labels'].get(flag_for.upper(), humanize(flag_for))} (status flag)"
                description = ("NCES status/imputation code for the value: R reported, B/Z/A and other letters mark values "
                               "that were imputed, implied, not applicable or otherwise adjusted. See the NCES data dictionary for this table.")
                unit = "category"
            else:
                label = info["labels"].get(raw) or humanize(name)
                description = info["desc"].get(raw) or ""
                unit = ""
                if raw in info["values"] and 1 < len(info["values"][raw]) <= 120:
                    for code, lab in info["values"][raw].items():
                        vals.append(("ipeds", fam, name, str(code), lab))
            rows.append(("ipeds", fam, name, label, description, unit, yrs[0], yrs[-1], table_cav if name in ("unitid",) else ""))
    return rows, vals


# ------------------------------------------------------------------------------------ PSS
PSS_DERIVED = {
    "row_id": ("Row ID", "Position of the school record in the national public-use file (stable identifier within a survey)."),
    "ppin": ("Private school PIN", "NCES permanent identification number; the cross-year merge key where present."),
    "year": ("Survey year", "Fall year the survey began (2023 = 2023-24)."),
    "school_year": ("Survey school year", "School year label such as 2023-24."),
    "source_file": ("Source file", "Name of the NCES file this row was built from."),
    "dimension": ("Dimension", "Kind of breakdown: total, grade, race, sex or teachers."),
    "category": ("Category", "The grade, race/ethnicity, sex or teacher category the value describes."),
    "value": ("Value", "Student or teacher count (or ratio/FTE), NULL when missing or not applicable."),
    "value_flag": ("Value flag", "reported, missing (blank) or not_applicable (negative source code)."),
    "imputation_flag": ("Imputation flag", "NCES imputation code for the source item (F_<item>), blank when none."),
    "lat": ("Latitude", "Latitude in decimal degrees as provided by NCES for the survey."),
    "lon": ("Longitude", "Longitude in decimal degrees as provided by NCES for the survey."),
    "name": ("School name", "School name (PINST)."), "address": ("Street address", "Mailing street address (PADDRS)."),
    "city": ("City", "Mailing city."), "zip": ("ZIP", "Mailing ZIP code."), "state_abbrev": ("State", "State postal abbreviation."),
    "enrollment_total": ("Total enrollment", "Total student enrollment (NUMSTUDS, derived by NCES from the reported and imputed items)."),
    "teachers_fte": ("Teachers (FTE)", "Number of K-12 teachers, full-time equivalent (NUMTEACH)."),
    "student_teacher_ratio": ("Student-teacher ratio", "Students per FTE teacher (STTCH_RT)."),
    "ulocale": ("Locale code", "NCES urban-centric locale code of the school location."),
    "county_fips": ("County FIPS", "5-digit county FIPS code, updated to the survey's geography."),
    "grade_low": ("Lowest grade", "Lowest grade offered (LOGR)."), "grade_high": ("Highest grade", "Highest grade offered (HIGR)."),
}


def pss_dictionary_rows() -> tuple[list[tuple], list[tuple]]:
    from .ipeds_build import years_from_str
    from .pss import VALUE_LABELS, load_map

    base = DOCS_DATA / "pss"
    if not base.exists():
        return [], []
    caveats = yaml.safe_load((CONFIG_DIR / "caveats.yml").read_text(encoding="utf-8")) or {}
    m = load_map()
    vl = (yaml.safe_load(VALUE_LABELS.read_text(encoding="utf-8")) or {}).get("values", {}) if VALUE_LABELS.exists() else {}
    by_name: dict[str, list[tuple[str, dict]]] = {}
    for raw, spec in m["columns"].items():
        by_name.setdefault(spec["name"], []).append((raw, spec))
    rows, vals = [], []
    for table_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        t = table_dir.name
        cav = (caveats.get(f"pss.{t}") or {}).get("caveat", "")
        for name, years in _parquet_presence(table_dir).items():
            yrs = years or [int(f.stem) for f in table_dir.glob("*.parquet")]
            label, description, unit = (humanize(name), "", "")
            if name in PSS_DERIVED:
                label, description = PSS_DERIVED[name]
            entries = by_name.get(name, []) if t == "schools" else []
            if entries:
                ys: set[int] = set()
                for raw, spec in entries:
                    ys |= years_from_str(spec["years"])
                    if spec.get("label") and name not in PSS_DERIVED:
                        label = spec["label"]
                if ys:
                    yrs = sorted(ys)
                flag_for = entries[0][1].get("flag_for")
                if flag_for:
                    label = f"{flag_for.upper()} imputation flag"
                    description = "NCES imputation flag for the item of the same name (0 = reported; other codes = imputed or adjusted)."
                    unit = "category"
                for raw, _ in entries:
                    for code, lab in vl.get(raw, {}).items():
                        vals.append(("pss", t, name, str(code), lab))
            rows.append(("pss", t, name, label, description, unit, min(yrs), max(yrs), cav if name in ("row_id", "value") else ""))
    # de-duplicate value labels (several raw columns can share a name)
    vals = sorted(set(vals))
    return rows, vals
