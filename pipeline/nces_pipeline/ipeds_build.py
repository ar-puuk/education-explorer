"""Build IPEDS tables for one state: staging by UNITID, compact year-ranged column maps, Parquet."""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import yaml

from .config import DATA_RAW, DOCS_DATA, SCHEMAS, State
from .ipeds_files import IpedsFile, data_csv, data_version, dict_xlsx, select
from .parquet import write_parquet
from .rawio import header_of, read_sql, run_copy
from .schema import SchemaDrift

MAPS = SCHEMAS / "ipeds"
RANK = {"BIGINT": 0, "DOUBLE": 1, "VARCHAR": 2}


# ---------------------------------------------------------------- year ranges ("2000-2004,2006")
def years_to_str(ys: list[int]) -> str:
    ys = sorted(set(ys))
    out, i = [], 0
    while i < len(ys):
        j = i
        while j + 1 < len(ys) and ys[j + 1] == ys[j] + 1:
            j += 1
        out.append(str(ys[i]) if i == j else f"{ys[i]}-{ys[j]}")
        i = j + 1
    return ",".join(out)


def years_from_str(s: str) -> set[int]:
    out: set[int] = set()
    for part in str(s).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out |= set(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


def q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


# ---------------------------------------------------------------- state institutions
def _ids_path(state: State) -> Path:
    return DATA_RAW / "_stage" / state.abbrev.lower() / "ipeds_unitids.json"


def state_unitids(state: State) -> set[str]:
    """UNITIDs that were ever located in the state according to any year's directory (HD) file."""
    hd = [f for f in select() if f.family == "hd"]
    sig = [f"{f.name}:{(DATA_RAW / f.rel).stat().st_size}" for f in hd if (DATA_RAW / f.rel).exists()]
    p = _ids_path(state)
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        if d["sig"] == sig:
            return set(d["ids"])
    con = duckdb.connect()
    ids: set[str] = set()
    for f in hd:
        if not (DATA_RAW / f.rel).exists():
            continue
        csv = data_csv(f)
        cols = {c.upper(): c for c in header_of(csv)}
        if "STABBR" not in cols or "UNITID" not in cols:
            raise SchemaDrift(f"{f.name}: no STABBR/UNITID in the directory file")
        rows = con.execute(
            f"SELECT DISTINCT lpad(trim({q(cols['UNITID'])}), 6, '0') FROM {read_sql(csv)} "
            f"WHERE upper(trim({q(cols['STABBR'])})) = '{state.abbrev.upper()}'"
        ).fetchall()
        ids |= {r[0] for r in rows}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"sig": sig, "ids": sorted(ids)}), encoding="utf-8", newline="\n")
    return ids


def staged_path(f: IpedsFile, state: State) -> Path:
    return DATA_RAW / "_stage" / state.abbrev.lower() / f"ipeds_{f.family}_{f.year}.parquet"


def stage(f: IpedsFile, state: State, ids: set[str]) -> Path | None:
    """State rows only, every column as VARCHAR. None when the file has no UNITID column."""
    csv = data_csv(f)
    dest = staged_path(f, state)
    stamp = dest.with_suffix(".stamp")
    sig = f"{csv.stat().st_size}:{csv.stat().st_mtime_ns}:{len(ids)}"
    if dest.exists() and stamp.exists() and stamp.read_text() == sig:
        return dest
    cols = {c.upper(): c for c in header_of(csv)}
    if "UNITID" not in cols:
        return None
    con = duckdb.connect()
    con.execute("CREATE TEMP TABLE ids(id VARCHAR)")
    con.executemany("INSERT INTO ids VALUES (?)", [(i,) for i in sorted(ids)])
    tmp = dest.with_suffix(".tmp")
    run_copy(con, lambda par: (
        f"COPY (SELECT * FROM {read_sql(csv, parallel=par)} WHERE lpad(trim({q(cols['UNITID'])}), 6, '0') IN (SELECT id FROM ids)) "
        f"TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"))
    tmp.replace(dest)
    stamp.write_text(sig)
    return dest


# ---------------------------------------------------------------- maps
def map_file(family: str) -> Path:
    return MAPS / f"{family}.yml"


def load_family_map(family: str) -> dict:
    p = map_file(family)
    if not p.exists():
        raise SchemaDrift(f"No column map for ipeds/{family}. Run: python -m nces_pipeline bootstrap-maps --source ipeds")
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    for raw, spec in d["columns"].items():
        if spec.get("ignore") and not spec.get("reason"):
            raise SchemaDrift(f"{p}: ignored column {raw} needs a reason")
    return d


def expected_columns(d: dict, year: int) -> set[str]:
    return {raw for raw, spec in d["columns"].items() if year in years_from_str(spec["years"])}


def check_header(family: str, year: int, d: dict, raw_cols: list[str]) -> None:
    raw = {c.upper() for c in raw_cols}
    want = expected_columns(d, year)
    new, gone = sorted(raw - want), sorted(want - raw)
    if not new and not gone:
        return
    import difflib

    lines = [f"SCHEMA DRIFT in ipeds/{family}/{year} (map: {map_file(family)})"]
    for c in new:
        near = difflib.get_close_matches(c, gone or list(d["columns"]), n=2, cutoff=0.6)
        lines.append(f"  + {c} not in the map" + (f" (nearest known: {', '.join(near)})" if near else ""))
    for c in gone:
        near = difflib.get_close_matches(c, new, n=2, cutoff=0.6)
        lines.append(f"  - {c} mapped for {year} but missing" + (f" (maybe renamed to: {', '.join(near)})" if near else ""))
    lines.append("Edit the YAML map (add the column with `years` including this year, or fix `years`) and re-run.")
    raise SchemaDrift("\n".join(lines))


def _dict_types(files: list[IpedsFile]) -> dict[str, str]:
    """varName -> 'A' (alpha) | 'N' (numeric) from the newest dictionary that lists it."""
    con = duckdb.connect()
    con.execute("INSTALL excel; LOAD excel;")
    out: dict[str, str] = {}
    for f in sorted(files, key=lambda x: -x.year):
        x = dict_xlsx(f)
        if not x:
            continue
        from .dictionary import _sheet_rows

        for r in _sheet_rows(con, x, "Varlist"):
            if r[1] and r[1].upper() not in out:
                out[r[1].upper()] = (r[2] or "").upper()
    return out


def bootstrap_family(family: str, state: State, files: list[IpedsFile], ids: set[str], force: bool = False) -> Path | None:
    p = map_file(family)
    if p.exists() and not force:
        return p
    con = duckdb.connect()
    cols_years: dict[str, list[int]] = {}
    order: list[str] = []
    types: dict[str, str] = {}
    staged: list[tuple[IpedsFile, Path]] = []
    for f in files:
        sp = stage(f, state, ids)
        if sp is None:
            continue
        staged.append((f, sp))
        raw_hdr = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{sp.as_posix()}')").fetchall()]
        hdr = [c.upper() for c in raw_hdr]
        for c in hdr:
            if c not in cols_years:
                cols_years[c] = []
                order.append(c)
            cols_years[c].append(f.year)
        aggs = []
        for raw in raw_hdr:
            v = f"NULLIF(TRIM({q(raw)}), '')"
            # note: TRY_CAST('40.76' AS BIGINT) rounds to 41, so integers are detected with a regex
            aggs += [f"count(*) FILTER (WHERE {v} IS NOT NULL AND NOT regexp_matches({v}, '^[+-]?[0-9]+$'))",
                     f"count(*) FILTER (WHERE {v} IS NOT NULL AND TRY_CAST({v} AS DOUBLE) IS NULL)"]
        stats = con.execute(f"SELECT {', '.join(aggs)} FROM read_parquet('{sp.as_posix()}')").fetchone()
        for i, c in enumerate(hdr):
            nonint, nonnum = stats[2 * i], stats[2 * i + 1]
            t = "VARCHAR" if nonnum else ("DOUBLE" if nonint else "BIGINT")
            if c not in types or RANK[t] > RANK[types[c]]:
                types[c] = t
    if not staged:
        return None
    dtypes = _dict_types(files)
    cols: dict[str, dict] = {}
    present = set(cols_years)
    for c in order:
        flag_of = c[1:] if c.startswith("X") and c[1:] in present else None
        if c == "UNITID":
            spec = {"name": "unitid", "type": "VARCHAR"}
        elif flag_of:
            spec = {"name": flag_of.lower() + "_flag", "type": "VARCHAR", "flag_for": flag_of.lower()}
        else:
            t = "VARCHAR" if dtypes.get(c) == "A" else types[c]
            spec = {"name": c.lower(), "type": t}
        spec["years"] = years_to_str(cols_years[c])
        cols[c] = spec
    # a short, stable unique key for validation
    key = _find_key(con, [sp for _, sp in staged], cols)
    doc = {"source": "ipeds", "family": family, "key": key, "columns": cols}
    MAPS.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(doc, sort_keys=False, width=160), encoding="utf-8", newline="\n")
    return p


def _find_key(con, staged: list[Path], cols: dict[str, dict]) -> list[str]:
    """UNITID plus the fewest dimension columns that make rows unique within each year file.

    Greedy: repeatedly add the low-cardinality, non-flag column that removes the most duplicate groups
    (ties go to the column that comes first in the file)."""
    paths = ", ".join(f"'{p.as_posix()}'" for p in staged)
    base = f"read_parquet([{paths}], union_by_name=true, filename=true)"
    names = {raw: spec["name"] for raw, spec in cols.items()}
    key = ["UNITID"]

    def dups(k: list[str]) -> int:
        kk = ", ".join(q(c) for c in [*k, "filename"])  # unique within each year file
        # excess rows (rows minus distinct keys): shrinks monotonically as the key is refined
        return con.execute(f"SELECT coalesce(sum(c - 1), 0) FROM (SELECT count(*) c FROM {base} GROUP BY {kk})").fetchone()[0]

    cur = dups(key)
    if not cur:
        return ["unitid"]
    cands = []
    for raw, spec in cols.items():
        if raw == "UNITID" or spec.get("flag_for"):
            continue
        nd = con.execute(f"SELECT count(DISTINCT {q(raw)}) FROM {base}").fetchone()[0]
        if 1 < nd <= 1500:
            cands.append(raw)
    while cur and len(key) < 7:
        best, best_n = None, cur
        for raw in cands:
            if raw in key:
                continue
            n = dups([*key, raw])
            if n < best_n:
                best, best_n = raw, n
        if best is None:
            break
        key.append(best)
        cur = best_n
    return [names[k] for k in key]  # validation reports anything still duplicated


# ---------------------------------------------------------------- build
def col_sql(raw: str, spec: dict) -> str:
    s = f"NULLIF(TRIM({q(raw)}), '')"
    t = spec["type"]
    if spec["name"] == "unitid":
        return f"lpad({s}, 6, '0')"
    if t == "VARCHAR":
        return s
    return f"TRY_CAST({s} AS {t})"


def _check_casts(con, sp: Path, d: dict, rawname: dict, f: IpedsFile) -> None:
    """Fail loudly if a typed column would silently lose values (e.g. text in a numeric column)."""
    checks, names = [], []
    for raw, spec in d["columns"].items():
        if spec.get("ignore") or spec["type"] == "VARCHAR" or raw not in rawname or f.year not in years_from_str(spec["years"]):
            continue
        v = f"NULLIF(TRIM({q(rawname[raw])}), '')"
        checks.append(f"count(*) FILTER (WHERE {v} IS NOT NULL AND TRY_CAST({v} AS {spec['type']}) IS NULL)")
        names.append(raw)
    if not checks:
        return
    row = con.execute(f"SELECT {', '.join(checks)} FROM read_parquet('{sp.as_posix()}')").fetchone()
    bad = [f"{n} ({c} values)" for n, c in zip(names, row) if c]
    if bad:
        raise SchemaDrift(f"TYPE DRIFT in ipeds/{f.family}/{f.year}: values cannot be cast to the mapped type: {', '.join(bad[:8])}. "
                          f"Widen the column type in {map_file(f.family)}.")


def build_ipeds(state: State, years: list[int] | None = None, families: list[str] | None = None) -> list[dict]:
    ids = state_unitids(state)
    con = duckdb.connect()
    report = []
    for f in select():
        if families and f.family not in families:
            continue
        if years and f.year not in years:
            continue
        if not (DATA_RAW / f.rel).exists():
            continue
        sp = stage(f, state, ids)
        if sp is None:
            print(f"  skip {f.name}: no UNITID column")
            continue
        d = load_family_map(f.family)
        hdr = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{sp.as_posix()}')").fetchall()]
        check_header(f.family, f.year, d, hdr)
        rawname = {c.upper(): c for c in hdr}
        parts = [f"{f.year}::INTEGER AS year"]
        for raw, spec in d["columns"].items():
            if spec.get("ignore"):
                continue
            if raw in rawname and f.year in years_from_str(spec["years"]):
                parts.append(f"{col_sql(rawname[raw], spec)} AS {q(spec['name'])}")
            else:
                parts.append(f"CAST(NULL AS {spec['type']}) AS {q(spec['name'])}")
        parts.append(f"'{data_version(f)}' AS data_version")
        parts.append(f"'{data_csv(f).name}' AS source_file")
        _check_casts(con, sp, d, rawname, f)
        sql = f"SELECT {', '.join(parts)} FROM read_parquet('{sp.as_posix()}')"
        order = [c for c in d["key"]] or ["unitid"]
        n = write_parquet(con, sql, DOCS_DATA / "ipeds" / f.family / f"{f.year}.parquet", order)
        report.append({"table": f.family, "year": f.year, "rows": n})
        print(f"  ipeds.{f.family} {f.year}: {n} rows")
    return report


def bootstrap_all(state: State, force: bool = False) -> None:
    ids = state_unitids(state)
    by: dict[str, list[IpedsFile]] = {}
    for f in select():
        if (DATA_RAW / f.rel).exists():
            by.setdefault(f.family, []).append(f)
    for fam, files in sorted(by.items()):
        p = bootstrap_family(fam, state, sorted(files, key=lambda x: x.year), ids, force=force)
        print("map:", fam, "->", "skipped (no UNITID)" if p is None else p.name)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
