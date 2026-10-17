"""Build the modern-shaped CCD tables for legacy years (1997-98 to 2013-14) from the staged wide files.

Output goes into the same tables and schemas as the modern build (school_directory, school_location, membership,
lunch, staff; district_directory, district_membership, district_staff) so the app and validation treat every year
alike. The wide as-published legacy tables are kept too (legacy_school, legacy_district) with every column.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import yaml

from .ccd_build import FLAG_SQL, canonical_columns, num_value, q, sql_str
from .ccd_legacy import FIRST_LEGACY, LAST_LEGACY, stage_legacy
from .ccd_topics import GRADES, RACES, SEXES, STAFF_WIDE, TOPICS
from .config import DOCS_DATA, SCHEMAS, State
from .ipeds_build import RANK, years_from_str, years_to_str
from .parquet import write_parquet
from .schema import SchemaDrift
from .typecheck import check_casts

NOCAT = "No Category Codes"
STATUS = {"1": "Open", "2": "Closed", "3": "New", "4": "Added", "5": "Changed Boundary/Agency", "6": "Inactive",
          "7": "Future", "8": "Reopened"}
SCH_TYPE = {"1": "Regular School", "2": "Special Education School", "3": "Career and Technical School", "4": "Alternative School"}
LEVEL = {"1": "Elementary", "2": "Middle", "3": "High", "4": "Other", "N": "Not applicable", "M": "Not reported"}
CHARTER = {"1": "Yes", "2": "No", "N": "Not applicable", "M": "Not reported"}
LEA_TYPE = {"1": "Regular public school district that is not a component of a supervisory union",
            "2": "Regular public school district that is a component of a supervisory union",
            "3": "Supervisory union administrative center", "4": "Service agency", "5": "State agency",
            "6": "Federal agency", "7": "Independent charter district", "8": "Other education agency",
            "9": "Specialized public school district"}
LEGACY_MAPS = SCHEMAS / "ccd_legacy"
LEGACY_RACES = {**RACES}
LEGACY_SEXES = {**SEXES, "U": "Not Specified"}
EXTRA_STAFF = {"AIDES": "Paraprofessionals/Instructional Aides", "TOTDPL": None, "TOTOHC": None}


def _recode(expr: str, mapping: dict[str, str]) -> str:
    whens = " ".join(f"WHEN {sql_str(k)} THEN {sql_str(v)}" for k, v in mapping.items())
    return f"CASE {expr} {whens} ELSE NULL END"


def _suffix_used(cols: list[str], year: int, probe: str) -> str:
    """'98' when the file's names carry the survey-year suffix (SCHNAM98), else ''."""
    yy = f"{year % 100:02d}"
    return yy if probe + yy in cols else ""


def normalize(con: duckdb.DuckDBPyConnection, staged: Path, year: int, probe: str) -> dict[str, str]:
    """Create view `w` with upper-case, suffix-free base names. Returns {base: raw}."""
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{staged.as_posix()}')").fetchall()]
    yy = _suffix_used([c.upper() for c in cols], year, probe)
    names: dict[str, str] = {}
    for raw in cols:
        base = raw.upper()
        if yy and base.endswith(yy) and len(base) > len(yy) + 1:
            base = base[: -len(yy)]
        if base in names:
            raise SchemaDrift(f"legacy {staged.name}: columns {names[base]} and {raw} both normalize to {base}")
        names[base] = raw
    return names


def _t(names: dict[str, str], base: str) -> str | None:
    raw = names.get(base)
    return f"NULLIF(TRIM({q(raw)}), '')" if raw else None


def _pad(expr: str | None, n: int) -> str:
    return "CAST(NULL AS VARCHAR)" if expr is None else f"CASE WHEN {expr} IS NULL THEN NULL ELSE lpad({expr}, {n}, '0') END"


def _sel(expr: str | None, typ: str = "VARCHAR") -> str:
    return f"CAST(NULL AS {typ})" if expr is None else expr


def _meta(year: int, source: str) -> str:
    return (f"{year}::INTEGER AS year, {sql_str(f'{year}-{(year + 1) % 100:02d}')} AS school_year, "
            f"'legacy' AS data_version, {sql_str(source)} AS source_file")


def _frame(cols: list[tuple[str, str]], exprs: dict[str, str]) -> str:
    return ", ".join(f"{exprs[n]} AS {q(n)}" if n in exprs else f"CAST(NULL AS {t}) AS {q(n)}" for n, t in cols)


def _long_rows(names: dict[str, str], level: str) -> list[dict]:
    """Unpivot specs (source base name + dimension labels) for membership-like wide columns."""
    out = []
    for base in names:
        if m := re.match(r"^(AM|AS|HI|BL|WH|HP|TR)(PK|KG|\d\d|UG|AE)(M|F|U)$", base):
            out.append({"source": base, "grade": GRADES.get(m.group(2)), "race": LEGACY_RACES[m.group(1)],
                        "sex": LEGACY_SEXES[m.group(3)], "total_indicator": "Category Set A - By Race/Ethnicity; Sex; Grade"})
        elif m := re.match(r"^(PK|KG|G\d\d|UG|AE)$", base):
            g = m.group(1).removeprefix("G")
            out.append({"source": base, "grade": GRADES.get(g), "race": NOCAT, "sex": NOCAT, "total_indicator": "Subtotal 4 - By Grade"})
        elif base == "MEMBER":
            out.append({"source": base, "grade": NOCAT, "race": NOCAT, "sex": NOCAT, "total_indicator": "Education Unit Total"})
        elif base in ("AM", "AS", "HI", "BL", "WH", "HP", "TR"):
            out.append({"source": base, "grade": NOCAT, "race": LEGACY_RACES[base], "sex": NOCAT,
                        "total_indicator": "Subtotal - By Race/Ethnicity (all grades)"})
        elif base in ("IND", "ASIAN", "HISP", "BLACK", "WHITE", "PACIFIC", "TWO") and level == "school":
            race = {"IND": RACES["AM"], "ASIAN": RACES["AS"], "HISP": RACES["HI"], "BLACK": RACES["BL"], "WHITE": RACES["WH"],
                    "PACIFIC": RACES["HP"], "TWO": RACES["TR"]}[base]
            out.append({"source": base, "grade": NOCAT, "race": race, "sex": NOCAT, "total_indicator": "Subtotal - By Race/Ethnicity (all grades)"})
    return [o for o in out if o["grade"]]


def _unpivot_sql(table: str, names: dict[str, str], specs: list[dict], year: int, cols: list[tuple[str, str]], value: str,
                 dims: tuple[str, ...], id_exprs: dict[str, str], source: str, value_type: str = "INTEGER") -> str | None:
    parts = []
    for u in specs:
        raw = names.get(u["source"])
        if not raw:
            continue
        s = f"NULLIF(TRIM({q(raw)}), '')"
        ex = dict(id_exprs)
        ex.update({d: sql_str(u[d]) for d in dims})
        ex[value] = num_value(s, value_type)
        ex["value_flag"] = FLAG_SQL.format(s=s)
        parts.append(f"SELECT {_meta(year, source)}, {_frame(cols, ex)} FROM w")
    return " UNION ALL ".join(parts) if parts else None


# ---------------------------------------------------------------------------------------------- build
def build_legacy(state: State) -> list[dict]:
    bootstrap_legacy_maps(state)
    con = duckdb.connect()
    report: list[dict] = []
    for year in range(FIRST_LEGACY, LAST_LEGACY + 1):
        for level in ("school", "district"):
            staged = stage_legacy(year, level, state)
            if staged is None:
                print(f"  legacy {level} {year}: no readable file")
                continue
            probe = "SCHNAM" if level == "school" else "NAME"
            names = normalize(con, staged, year, probe)
            _STAGED[(year, level)] = staged
            check_legacy_map(level, year, names)
            con.execute("DROP VIEW IF EXISTS w")
            con.execute(f"CREATE VIEW w AS SELECT * FROM read_parquet('{staged.as_posix()}')")
            src = staged.name
            if level == "school":
                report += _school_tables(con, names, year, src)
            else:
                report += _district_tables(con, names, year, src)
    return report


def _out(topic: str, year: int) -> Path:
    return DOCS_DATA / "ccd" / topic / f"{year}.parquet"


def _school_tables(con, names: dict[str, str], year: int, src: str) -> list[dict]:
    t = lambda b: _t(names, b)
    rep = []
    # --- directory
    canon = canonical_columns(TOPICS["school_directory"])
    ex = {
        "fipst": _pad(t("FIPST") or t("FIPS"), 2), "ncessch": _pad(t("NCESSCH"), 12), "leaid": _pad(t("LEAID"), 7),
        "school_name": _sel(t("SCHNAM")), "lea_name": _sel(t("LEANM")), "st_leaid": _sel(t("STID")), "st_schid": _sel(t("SEASCH")),
        "mail_street1": _sel(t("MSTREE")), "mail_city": _sel(t("MCITY")), "mail_state": _sel(t("MSTATE")),
        "mail_zip": _sel(t("MZIP")), "mail_zip4": _sel(t("MZIP4")), "street1": _sel(t("LSTREE")), "city": _sel(t("LCITY")),
        "state": _sel(t("LSTATE")), "zip": _sel(t("LZIP")), "zip4": _sel(t("LZIP4")), "phone": _sel(t("PHONE")),
        "school_type_code": _sel(t("TYPE")), "status_code": _sel(t("STATUS")),
        "union_code": _sel(t("UNION")), "grade_low": _sel(t("GSLO")), "grade_high": _sel(t("GSHI")),
        "state_abbrev": _sel(t("LSTATE") or t("MSTATE")),
    }
    if t("TYPE"):
        ex["school_type"] = _recode(t("TYPE"), SCH_TYPE)
    if t("STATUS"):
        ex["status"] = _recode(t("STATUS"), STATUS)
    if t("LEVEL"):
        ex["level"] = _recode(t("LEVEL"), LEVEL)
    if t("CHARTR"):
        ex["charter"] = _recode(t("CHARTR"), CHARTER)
    sql = f"SELECT {_meta(year, src)}, {_frame(canon, ex)} FROM w WHERE {_pad(t('NCESSCH'), 12)} IS NOT NULL"
    n = write_parquet(con, sql, _out("school_directory", year), ["ncessch", "year"])
    rep.append({"table": "school_directory", "year": year, "rows": n})
    # --- location (coordinates exist from 1999-00; locale code is as published: old 1-8 scheme before 2006)
    loc_cols = _location_columns()
    lat = t("LATCOD")
    ex = {
        "year": f"{year}::INTEGER", "school_year": sql_str(f"{year}-{(year + 1) % 100:02d}"), "source_file": sql_str(src),
        "ncessch": _pad(t("NCESSCH"), 12), "leaid": _pad(t("LEAID"), 7), "school_name": _sel(t("SCHNAM")),
        "street": _sel(t("LSTREE")), "city": _sel(t("LCITY")), "state": _sel(t("LSTATE")), "zip": _sel(t("LZIP")),
        "zip4": _sel(t("LZIP4")), "fipst": _pad(t("FIPST") or t("FIPS"), 2), "county_fips": _sel(t("CONUM")),
        "county_name": _sel(t("CONAME")), "locale": _sel(t("ULOCAL") or t("LOCALE")), "cd": _sel(t("CDCODE")),
        "lat": f"CASE WHEN TRY_CAST({lat} AS DOUBLE) BETWEEN 15 AND 72 THEN TRY_CAST({lat} AS DOUBLE) END" if lat else "CAST(NULL AS DOUBLE)",
        "lon": (f"CASE WHEN TRY_CAST({t('LONCOD')} AS DOUBLE) BETWEEN -180 AND -60 THEN TRY_CAST({t('LONCOD')} AS DOUBLE) END"
                if t("LONCOD") else "CAST(NULL AS DOUBLE)"),
        "coord_source": "'ccd_legacy'", "coord_approximate": "FALSE",
    }
    sql = f"SELECT {_frame(loc_cols, ex)} FROM w WHERE {_pad(t('NCESSCH'), 12)} IS NOT NULL"
    n = write_parquet(con, sql, _out("school_location", year), ["ncessch"])
    rep.append({"table": "school_location", "year": year, "rows": n})
    # --- membership (long)
    cols = canonical_columns(TOPICS["membership"])
    ids = {"fipst": _pad(t("FIPST") or t("FIPS"), 2), "ncessch": _pad(t("NCESSCH"), 12), "leaid": _pad(t("LEAID"), 7),
           "state_abbrev": _sel(t("LSTATE") or t("MSTATE"))}
    u = _unpivot_sql("membership", names, _long_rows(names, "school"), year, cols, "student_count",
                     TOPICS["membership"].dims, ids, src)
    if u:
        n = write_parquet(con, f"SELECT * FROM ({u})", _out("membership", year), list(TOPICS["membership"].sort) + ["year"])
        rep.append({"table": "membership", "year": year, "rows": n})
    # --- lunch (1998 on), staff (FTE)
    lunch_specs = [{"source": "FRELCH", "data_group": "Free and Reduced-price Lunch Table", "lunch_program": "Free lunch qualified", "total_indicator": "Category Set A"},
                   {"source": "REDLCH", "data_group": "Free and Reduced-price Lunch Table", "lunch_program": "Reduced-price lunch qualified", "total_indicator": "Category Set A"},
                   {"source": "TOTFRL", "data_group": "Free and Reduced-price Lunch Table", "lunch_program": NOCAT, "total_indicator": "Education Unit Total"}]
    cols = canonical_columns(TOPICS["lunch"])
    u = _unpivot_sql("lunch", names, lunch_specs, year, cols, "student_count", TOPICS["lunch"].dims, ids, src)
    if u:
        n = write_parquet(con, f"SELECT * FROM ({u})", _out("lunch", year), list(TOPICS["lunch"].sort) + ["year"])
        rep.append({"table": "lunch", "year": year, "rows": n})
    cols = canonical_columns(TOPICS["staff"])
    u = _unpivot_sql("staff", names, [{"source": "FTE", "total_indicator": "Education Unit Total"}], year, cols, "teachers",
                     TOPICS["staff"].dims, ids, src, "DOUBLE")
    if u:
        n = write_parquet(con, f"SELECT * FROM ({u})", _out("staff", year), list(TOPICS["staff"].sort) + ["year"])
        rep.append({"table": "staff", "year": year, "rows": n})
    # --- wide as-published table
    rep.append(_wide(con, names, year, "school", src))
    print(f"  legacy school {year}: " + ", ".join(f"{r['table']} {r['rows']}" for r in rep))
    return rep


def _district_tables(con, names: dict[str, str], year: int, src: str) -> list[dict]:
    t = lambda b: _t(names, b)
    rep = []
    canon = canonical_columns(TOPICS["district_directory"])
    ex = {
        "fipst": _pad(t("FIPST") or t("FIPS"), 2), "leaid": _pad(t("LEAID"), 7), "lea_name": _sel(t("NAME")),
        "st_leaid": _sel(t("STID")), "mail_street1": _sel(t("MSTREE")), "mail_city": _sel(t("MCITY")),
        "mail_state": _sel(t("MSTATE")), "mail_zip": _sel(t("MZIP")), "mail_zip4": _sel(t("MZIP4")),
        "street1": _sel(t("LSTREE")), "city": _sel(t("LCITY")), "state": _sel(t("LSTATE")), "zip": _sel(t("LZIP")),
        "zip4": _sel(t("LZIP4")), "phone": _sel(t("PHONE")), "lea_type_code": _sel(t("TYPE")), "union_code": _sel(t("UNION")),
        "grade_low": _sel(t("GSLO")), "grade_high": _sel(t("GSHI")), "operational_schools": _sel(t("SCH")),
        "state_abbrev": _sel(t("LSTATE") or t("MSTATE")), "charter_lea_code": _sel(t("AGCHRT")),
    }
    if t("TYPE"):
        ex["lea_type"] = _recode(t("TYPE"), LEA_TYPE)
    sql = f"SELECT {_meta(year, src)}, {_frame(canon, ex)} FROM w WHERE {_pad(t('LEAID'), 7)} IS NOT NULL"
    n = write_parquet(con, sql, _out("district_directory", year), ["leaid", "year"])
    rep.append({"table": "district_directory", "year": year, "rows": n})
    ids = {"fipst": _pad(t("FIPST") or t("FIPS"), 2), "leaid": _pad(t("LEAID"), 7), "state_abbrev": _sel(t("LSTATE") or t("MSTATE"))}
    cols = canonical_columns(TOPICS["district_membership"])
    u = _unpivot_sql("district_membership", names, _long_rows(names, "district"), year, cols, "student_count",
                     TOPICS["district_membership"].dims, ids, src)
    if u:
        n = write_parquet(con, f"SELECT * FROM ({u})", _out("district_membership", year), list(TOPICS["district_membership"].sort) + ["year"])
        rep.append({"table": "district_membership", "year": year, "rows": n})
    cols = canonical_columns(TOPICS["district_staff"])
    specs = [{"source": b, "staff_category": lab, "total_indicator": "Category Set A"} for b, lab in {**STAFF_WIDE, **{k: v for k, v in EXTRA_STAFF.items() if v}}.items()
             if b != "STAFF"]
    u = _unpivot_sql("district_staff", names, specs, year, cols, "staff_count", TOPICS["district_staff"].dims, ids, src, "DOUBLE")
    if u:
        n = write_parquet(con, f"SELECT * FROM ({u})", _out("district_staff", year), list(TOPICS["district_staff"].sort) + ["year"])
        rep.append({"table": "district_staff", "year": year, "rows": n})
    rep.append(_wide(con, names, year, "district", src))
    print(f"  legacy district {year}: " + ", ".join(f"{r['table']} {r['rows']}" for r in rep))
    return rep


def _location_columns() -> list[tuple[str, str]]:
    """Column list of the EDGE school_location tables (they must exist: build edge first)."""
    files = sorted((DOCS_DATA / "ccd" / "school_location").glob("2014.parquet")) or sorted((DOCS_DATA / "ccd" / "school_location").glob("*.parquet"))
    if not files:
        raise SchemaDrift("build the EDGE school locations first (python -m nces_pipeline build --source edge)")
    c = duckdb.connect()
    return [(r[0], r[1]) for r in c.execute(f"DESCRIBE SELECT * FROM read_parquet('{files[0].as_posix()}')").fetchall()]


# ---------------------------------------------------------------------------------------------- wide tables + maps
def _map_file(level: str) -> Path:
    return LEGACY_MAPS / f"{level}.yml"


def check_legacy_map(level: str, year: int, names: dict[str, str]) -> None:
    p = _map_file(level)
    if not p.exists():
        return  # first run: bootstrap_legacy_maps creates it
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    want = {c for c, s in d["columns"].items() if year in years_from_str(s["years"])}
    new, gone = sorted(set(names) - want), sorted(want - set(names))
    if new or gone:
        raise SchemaDrift(f"SCHEMA DRIFT in ccd_legacy/{level}/{year} (map: {p})\n"
                          + "".join(f"  + {c} not in the map\n" for c in new[:40]) + "".join(f"  - {c} mapped but missing\n" for c in gone[:40])
                          + "Edit the YAML map (or run bootstrap-maps --force) and re-run.")


def bootstrap_legacy_maps(state: State, force: bool = False) -> list[Path]:
    out = []
    for level in ("school", "district"):
        p = _map_file(level)
        if p.exists() and not force:
            out.append(p)
            continue
        con = duckdb.connect()
        cols_years: dict[str, list[int]] = {}
        order: list[str] = []
        types: dict[str, str] = {}
        labels: dict[str, str] = {}
        for year in range(FIRST_LEGACY, LAST_LEGACY + 1):
            staged = stage_legacy(year, level, state)
            if staged is None:
                continue
            names = normalize(con, staged, year, "SCHNAM" if level == "school" else "NAME")
            lab = json.loads(staged.with_suffix(".labels.json").read_text(encoding="utf-8"))
            for base, raw in names.items():
                if base not in cols_years:
                    cols_years[base] = []
                    order.append(base)
                cols_years[base].append(year)
                if lab.get(raw.upper()):
                    labels[base] = lab[raw.upper()]
            nat = json.loads(staged.with_suffix(".types.json").read_text(encoding="utf-8"))  # national counts
            for base, raw in names.items():
                nonint, nonnum = nat.get(raw.upper(), [0, 0])
                ty = "VARCHAR" if nonnum else ("DOUBLE" if nonint else "BIGINT")
                if base not in types or RANK[ty] > RANK[types[base]]:
                    types[base] = ty
        cols = {}
        force_str = re.compile(r"(ncessch|leaid|fipst|zip|phone|stid|seasch|schno|conum|cdcode|union|name|nam$|street|stree|city|state|type|status|level|chartr|locale|ulocal|gslo|gshi)", re.IGNORECASE)
        for base in order:
            ty = "VARCHAR" if force_str.search(base) else types[base]
            spec = {"name": base.lower(), "type": ty, "years": years_to_str(cols_years[base])}
            if base in ("LATCOD", "LONCOD"):
                spec.update({"type": "DOUBLE", "signed": True})
            if labels.get(base):
                spec["label"] = labels[base]
            cols[base] = spec
        LEGACY_MAPS.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump({"source": "ccd_legacy", "level": level, "key": ["ncessch" if level == "school" else "leaid"], "columns": cols},
                                    sort_keys=False, width=160, allow_unicode=True), encoding="utf-8", newline="\n")
        out.append(p)
    return out


_STAGED: dict[tuple[int, str], Path] = {}


def _staged_of(year: int, level: str) -> Path:
    return _STAGED[(year, level)]


def _wide(con, names: dict[str, str], year: int, level: str, src: str) -> dict:
    d = yaml.safe_load(_map_file(level).read_text(encoding="utf-8"))
    check_casts(con, _staged_of(year, level), [(names[b], sp["type"]) for b, sp in d["columns"].items()
                                                 if b in names and year in years_from_str(sp["years"])],
                f"ccd_legacy/{level}/{year}", "Re-run bootstrap-maps --force (types are sniffed from the national files).")
    sel = [f"{year}::INTEGER AS year"]
    for base, spec in d["columns"].items():
        if year not in years_from_str(spec["years"]) or base not in names:
            sel.append(f"CAST(NULL AS {spec['type']}) AS {q(spec['name'])}")
            continue
        raw = names[base]
        v = f"NULLIF(TRIM({q(raw)}), '')"
        ty = spec["type"]
        if ty == "VARCHAR":
            e = v
        elif spec.get("signed"):
            e = f"TRY_CAST({v} AS DOUBLE)"
        else:
            e = f"TRY_CAST({v} AS {ty})"
        sel.append(f"{e} AS {q(spec['name'])}")
    sel.append("'legacy' AS data_version")
    sel.append(f"{sql_str(src)} AS source_file")
    key = "ncessch" if level == "school" else "leaid"
    n = write_parquet(con, f"SELECT {', '.join(sel)} FROM w", DOCS_DATA / "ccd" / f"legacy_{level}" / f"{year}.parquet", [key])
    return {"table": f"legacy_{level}", "year": year, "rows": n}
