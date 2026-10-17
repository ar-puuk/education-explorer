"""NCES Private School Universe Survey (PSS): public-use microdata for every survey (1989-90 .. latest).

Every survey is read from its SAS7BDAT file (the only format available for all years; it also carries the
variable labels), filtered to the state, and written as VARCHAR Parquet. Maps are one YAML with per-column
year ranges (like IPEDS). Derived long tables: enrollment (grade, race, sex) and teachers.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyreadstat
import yaml

from .config import DATA_RAW, DOCS_DATA, SCHEMAS, State
from .fetch import client, download, unzip
from .ipeds_build import RANK, q, years_from_str, years_to_str
from .parquet import write_parquet
from .schema import SchemaDrift

BASE = "https://nces.ed.gov/surveys/pss/zip"
MAP = SCHEMAS / "pss" / "schools.yml"
VALUE_LABELS = SCHEMAS / "pss" / "value_labels.yml"

# survey start year -> (file name in the zip listing)
SURVEYS: dict[int, str] = {
    1989: "PSS8990_SAS7BDAT", 1991: "PSS9192_SAS7BDAT", 1993: "PSS9394_SAS7BDAT", 1995: "PSS9596_SAS7BDAT",
    1997: "PSS9798_SAS7BDAT", 1999: "PSS9900_SAS7BDAT", 2001: "PSS0102_SAS7BDAT", 2003: "PSS0304_SAS7BDAT",
    2005: "PSS0506_SAS7BDAT", 2007: "PSS0708_SAS7BDAT", 2009: "PSS0910_SAS7BDAT", 2011: "pss1112_pu_sas7bdat",
    2013: "pss1314_pu_sas7bdat", 2015: "pss1516_pu_sas7bdat", 2017: "pss1718_pu_sas7bdat",
    2019: "pss1920_pu_sas7bdat", 2021: "pss2122_pu_sas7bdat", 2023: "pss2324_pu_sas7bdat",
}

STATE_COLS = ["PSTABB", "ESTABB", "QSTABB", "RSTABB", "SSTABB", "STABB", "STATE", "PSTANSI", "SSTFIPS", "STFIPS"]


@dataclass(frozen=True)
class Survey:
    year: int
    name: str

    @property
    def url(self) -> str:
        return f"{BASE}/{self.name}.zip"

    @property
    def rel(self) -> str:
        return f"pss/{self.year}/{self.name.lower()}.zip"

    @property
    def label(self) -> str:
        return f"{self.year}-{(self.year + 1) % 100:02d}"


def surveys() -> list[Survey]:
    return [Survey(y, n) for y, n in sorted(SURVEYS.items())]


def fetch_pss(check_only: bool = False) -> int:
    n = 0
    if check_only:
        for s in surveys():
            have = (DATA_RAW / s.rel).exists()
            n += have
            if not have:
                print(f"  NEW PSS {s.label}: {s.url}")
        return n
    with client() as c:
        for s in surveys():
            p = download(s.url, s.rel, source="pss", release=s.label, c=c, skip_missing=True)
            if p is None:
                print(f"MISSING (404): {s.url}")
            else:
                n += 1
    return n


def sas_file(s: Survey) -> Path:
    folder = unzip(DATA_RAW / s.rel)
    fs = [p for p in folder.rglob("*") if p.suffix.lower() == ".sas7bdat"]
    if not fs:
        raise SystemExit(f"{s.name}: no sas7bdat in zip")
    return fs[0]


def _fmt(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v):
            return None
        return str(int(v)) if v == int(v) else repr(v)
    s = str(v).strip()
    return s or None


def _state_rows(cols: list[str], data: dict, state: State) -> list[int]:
    up = {c.upper(): c for c in cols}
    for cand in STATE_COLS:
        if cand not in up:
            continue
        col = data[up[cand]]
        sample = next((x for x in col if x not in (None, "") and not (isinstance(x, float) and math.isnan(x))), None)
        if sample is None:
            continue
        if isinstance(sample, str) and not sample.strip().isdigit():
            return [i for i, x in enumerate(col) if isinstance(x, str) and x.strip().upper() == state.abbrev.upper()]
        fips = int(state.fips)
        out = []
        for i, x in enumerate(col):
            try:
                if x not in (None, "") and int(float(x)) == fips:
                    out.append(i)
            except (TypeError, ValueError):
                pass
        return out
    raise SchemaDrift(f"PSS: no state column found among {STATE_COLS} in {cols[:20]}")


def stage_pss(s: Survey, state: State) -> Path:
    """State rows of one survey as VARCHAR Parquet (+ labels sidecar)."""
    dest = DATA_RAW / "_stage" / state.abbrev.lower() / f"pss_{s.year}.parquet"
    src = sas_file(s)
    stamp = dest.with_suffix(".stamp")
    sig = f"{src.stat().st_size}:{src.stat().st_mtime_ns}"
    if dest.exists() and stamp.exists() and stamp.read_text() == sig:
        return dest
    data, meta = pyreadstat.read_sas7bdat(str(src), output_format="dict")
    cols = list(meta.column_names)
    keep = _state_rows(cols, data, state)
    dest.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE t(row_id BIGINT, " + ", ".join(f"{q(c.upper())} VARCHAR" for c in cols) + ")")
    rows = [[i + 1] + [_fmt(data[c][i]) for c in cols] for i in keep]  # row_id = position in the national file
    con.executemany(f"INSERT INTO t VALUES ({', '.join(['?'] * (len(cols) + 1))})", rows)
    tmp = dest.with_suffix(".tmp")
    con.execute(f"COPY (SELECT * FROM t ORDER BY row_id) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    tmp.replace(dest)
    labels = {c.upper(): (l or "") for c, l in zip(cols, meta.column_labels)}
    dest.with_suffix(".labels.json").write_text(json.dumps(labels), encoding="utf-8", newline="\n")
    stamp.write_text(sig)
    return dest


# ------------------------------------------------------------------------------------ canonical names
ALIAS = {
    "PPIN": "ppin", "PINST": "name", "PADDRS": "address", "PCITY": "city", "PZIP": "zip", "PZIP4": "zip4",
    "PSTABB": "state_abbrev", "ESTABB": "state_abbrev", "QSTABB": "state_abbrev", "RSTABB": "state_abbrev",
    "SSTABB": "state_abbrev", "EZIP": "zip", "QZIP": "zip", "RZIP": "zip", "SZIP": "zip",
    "NUMSTUDS": "enrollment_total", "NUMTEACH": "teachers_fte", "STTCH_RT": "student_teacher_ratio",
    "LOCALE": "locale_old",
}
YEAR_SUFFIXED = {  # base names whose raw columns carry the survey year (LATITUDE24, ULOCALE12, LOGR2024...)
    "LATITUDE": "lat", "LONGITUDE": "lon", "ULOCALE": "ulocale", "PCNTY": "county_fips", "SLDLST": "sldlst",
    "SLDUST": "sldust", "STCD": "stcd", "LOGR": "grade_low", "HIGR": "grade_high",
}
FORCE_VARCHAR = re.compile(r"zip|phone|ppin|fips|cnty|stansi|stabb|sld|stcd|ulocale|^state$|^name$|address|city|^pinst$", re.IGNORECASE)


def canonical(raw: str) -> tuple[str, bool]:
    """(canonical name, is_signed_coordinate) for an upper-case raw column."""
    if raw in ALIAS:
        return ALIAS[raw], False
    m = re.match(r"^(LATITUDE|LONGITUDE|ULOCALE|PCNTY|SLDLST|SLDUST|STCD|LOGR|HIGR)(\d{2}|\d{4})$", raw)
    if m:
        return YEAR_SUFFIXED[m.group(1)], m.group(1) in ("LATITUDE", "LONGITUDE")
    if raw in ("LATITUDE", "LONGITUDE"):
        return YEAR_SUFFIXED[raw], True
    return raw.lower(), False


# ------------------------------------------------------------------------------------ maps
def load_map() -> dict:
    if not MAP.exists():
        raise SchemaDrift("No PSS column map. Run: python -m nces_pipeline bootstrap-maps --source pss")
    return yaml.safe_load(MAP.read_text(encoding="utf-8"))


def bootstrap(state: State, force: bool = False) -> Path:
    if MAP.exists() and not force:
        return MAP
    con = duckdb.connect()
    cols_years: dict[str, list[int]] = {}
    order: list[str] = []
    types: dict[str, str] = {}
    labels: dict[str, str] = {}
    for s in surveys():
        sp = stage_pss(s, state)
        for k, v in json.loads(sp.with_suffix(".labels.json").read_text(encoding="utf-8")).items():
            if v:
                labels[k] = v  # newest label wins (surveys iterate oldest -> newest)
        hdr = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{sp.as_posix()}')").fetchall() if r[0] != "row_id"]
        for c in hdr:
            if c not in cols_years:
                cols_years[c] = []
                order.append(c)
            cols_years[c].append(s.year)
        aggs = []
        for c in hdr:
            v = f"NULLIF(TRIM({q(c)}), '')"
            aggs += [f"count(*) FILTER (WHERE {v} IS NOT NULL AND NOT regexp_matches({v}, '^[+-]?[0-9]+$'))",
                     f"count(*) FILTER (WHERE {v} IS NOT NULL AND TRY_CAST({v} AS DOUBLE) IS NULL)"]
        stats = con.execute(f"SELECT {', '.join(aggs)} FROM read_parquet('{sp.as_posix()}')").fetchone()
        for i, c in enumerate(hdr):
            t = "VARCHAR" if stats[2 * i + 1] else ("DOUBLE" if stats[2 * i] else "BIGINT")
            if c not in types or RANK[t] > RANK[types[c]]:
                types[c] = t
    present = set(cols_years)
    cols: dict[str, dict] = {}
    by_name: dict[str, list[str]] = {}  # canonical name -> raw columns sharing it (disjoint years only)
    for c in order:
        flag_of = c[2:] if c.startswith("F_") and c[2:] in present else None
        if flag_of:
            spec = {"name": canonical(flag_of)[0] + "_flag", "type": "VARCHAR", "flag_for": canonical(flag_of)[0]}
            # F_<raw> belongs to <raw>: use the same shared name as its value column
        else:
            name, signed = canonical(c)
            t = "VARCHAR" if (FORCE_VARCHAR.search(name) or FORCE_VARCHAR.search(c)) else types[c]
            if signed:
                t = "DOUBLE"
            spec = {"name": name, "type": t}
            if signed:
                spec["signed"] = True
        ys = set(cols_years[c])
        clash = any(ys & set(cols_years[o]) for o in by_name.get(spec["name"], []))
        if clash:  # two columns of the same survey would collide: keep this one under its raw name
            spec["name"] = c.lower()
        by_name.setdefault(spec["name"], []).append(c)
        spec["years"] = years_to_str(cols_years[c])
        if labels.get(c):
            spec["label"] = labels[c]
        cols[c] = spec
    # columns sharing a name must share a type (widest wins)
    for name, raws in by_name.items():
        if len(raws) > 1:
            widest = max((cols[r]["type"] for r in raws), key=lambda t: RANK.get(t, 2))
            for r in raws:
                cols[r]["type"] = widest
    MAP.parent.mkdir(parents=True, exist_ok=True)
    MAP.write_text(yaml.safe_dump({"source": "pss", "table": "schools", "key": ["row_id"], "columns": cols},
                                  sort_keys=False, width=160, allow_unicode=True), encoding="utf-8", newline="\n")
    return MAP


def check_header(year: int, d: dict, raw_cols: list[str]) -> None:
    import difflib

    raw = {c.upper() for c in raw_cols if c != "row_id"}
    want = {c for c, spec in d["columns"].items() if year in years_from_str(spec["years"])}
    new, gone = sorted(raw - want), sorted(want - raw)
    if not new and not gone:
        return
    lines = [f"SCHEMA DRIFT in pss/{year} (map: {MAP})"]
    for c in new:
        near = difflib.get_close_matches(c, gone or list(d["columns"]), n=2, cutoff=0.6)
        lines.append(f"  + {c} not in the map" + (f" (nearest known: {', '.join(near)})" if near else ""))
    for c in gone:
        lines.append(f"  - {c} mapped for {year} but missing")
    lines.append("Edit schemas/pss/schools.yml (add the column with `years` including this year) and re-run.")
    raise SchemaDrift("\n".join(lines))


# ------------------------------------------------------------------------------------ derived tables
GRADES = {"P140": "Ungraded", "P150": "Nursery/prekindergarten", "P160": "Kindergarten", "P170": "Transitional kindergarten",
          "P180": "Transitional first grade", **{f"P{190 + 10 * i}": f"Grade {i + 1}" for i in range(12)}}
RACES = {"P320": "Hispanic or Latino", "P330": "White", "P325": "Black or African American", "P316": "Asian",
         "P318": "Native Hawaiian or Pacific Islander", "P310": "American Indian or Alaska Native",
         "P332": "Two or more races", "P315": "Asian or Pacific Islander (single category before 2009-10)"}
TEACHERS = {"P385": "Full-time teachers", "P390": "More than 3/4 time teachers", "P395": "More than 1/2 time teachers",
            "P400": "More than 1/4 time teachers", "P405": "Less than 1/4 time teachers", "P410": "Total teachers (headcount)",
            "NUMTEACH": "K-12 teachers (FTE)", "STTCH_RT": "Student-teacher ratio"}

FLAG = """CASE WHEN {s} IS NULL THEN 'missing'
  WHEN TRY_CAST({s} AS DOUBLE) < 0 THEN 'not_applicable' ELSE 'reported' END"""


def _value_sql(raw: str) -> tuple[str, str]:
    s = f"NULLIF(TRIM({q(raw)}), '')"
    v = f"CASE WHEN TRY_CAST({s} AS DOUBLE) >= 0 THEN TRY_CAST({s} AS DOUBLE) END"
    return v, FLAG.format(s=s)


def _derived_sql(sp: Path, year: int, hdr: set[str], spec: list[tuple[str, dict]]) -> str | None:
    parts = []
    for raw, dims in spec:
        if raw not in hdr:
            continue
        v, f = _value_sql(raw)
        d = ", ".join(f"'{val}' AS {k}" for k, val in dims.items())
        flagcol = f"F_{raw}"
        flag = f"coalesce(CAST({q(flagcol)} AS VARCHAR), '')" if flagcol in hdr else "''"
        ppin = f"NULLIF(TRIM({q('PPIN')}), '')" if "PPIN" in hdr else "CAST(NULL AS VARCHAR)"
        parts.append(f"SELECT row_id, {ppin} AS ppin, {year}::INTEGER AS year, {d}, {v} AS value, {f} AS value_flag, "
                     f"{flag} AS imputation_flag FROM read_parquet('{sp.as_posix()}')")
    return " UNION ALL ".join(parts) if parts else None


def build_pss(state: State) -> list[dict]:
    d = load_map()
    con = duckdb.connect()
    report = []
    for s in surveys():
        sp = stage_pss(s, state)
        hdr_list = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{sp.as_posix()}')").fetchall()]
        check_header(s.year, d, hdr_list)
        hdr = set(hdr_list)
        sel = [f"{s.year}::INTEGER AS year", "row_id"]
        chosen: dict[str, tuple[str, dict]] = {}
        out_types: dict[str, str] = {}
        for raw, spec in d["columns"].items():
            out_types.setdefault(spec["name"], spec["type"])
            if raw in hdr and s.year in years_from_str(spec["years"]):
                if spec["name"] in chosen:
                    raise SchemaDrift(f"pss/{s.year}: columns {chosen[spec['name']][0]} and {raw} both map to {spec['name']}")
                chosen[spec["name"]] = (raw, spec)
        for name, t in out_types.items():
            if name in chosen:
                raw, spec = chosen[name]
                v = f"NULLIF(TRIM({q(raw)}), '')"
                if t == "VARCHAR":
                    e = (rf"CASE WHEN {v} IS NULL THEN NULL WHEN regexp_matches({v}, '^-?[0-9]+\.0+$') "
                         rf"THEN regexp_replace({v}, '\.0+$', '') ELSE {v} END")
                elif spec.get("signed"):
                    e = f"TRY_CAST({v} AS DOUBLE)"
                else:
                    e = f"TRY_CAST({v} AS {t})"
                sel.append(f"{e} AS {q(name)}")
            else:
                sel.append(f"CAST(NULL AS {t}) AS {q(name)}")
        sel.append(f"'{s.label}' AS school_year")
        sel.append(f"'{sas_file(s).name}' AS source_file")
        n = write_parquet(con, f"SELECT {', '.join(sel)} FROM read_parquet('{sp.as_posix()}')",
                          DOCS_DATA / "pss" / "schools" / f"{s.year}.parquet", ["row_id"])
        report.append({"table": "schools", "year": s.year, "rows": n})
        enr = _derived_sql(sp, s.year, hdr,
                           [("P305", {"dimension": "total", "category": "All students"}),
                            ("NUMSTUDS", {"dimension": "total", "category": "All students (derived total)"}),
                            ("P340", {"dimension": "sex", "category": "Male"}),
                            *[(k, {"dimension": "grade", "category": v}) for k, v in GRADES.items()],
                            *[(k, {"dimension": "race", "category": v}) for k, v in RACES.items()]])
        if enr:
            n2 = write_parquet(con, f"SELECT * FROM ({enr})", DOCS_DATA / "pss" / "enrollment" / f"{s.year}.parquet",
                               ["row_id", "dimension", "category"])
            report.append({"table": "enrollment", "year": s.year, "rows": n2})
        tch = _derived_sql(sp, s.year, hdr, [(k, {"dimension": "teachers", "category": v}) for k, v in TEACHERS.items()])
        if tch:
            n3 = write_parquet(con, f"SELECT * FROM ({tch})", DOCS_DATA / "pss" / "teachers" / f"{s.year}.parquet",
                               ["row_id", "category"])
            report.append({"table": "teachers", "year": s.year, "rows": n3})
        print(f"  pss {s.label}: {n} schools")
    return report
