"""Validation: must pass before processed Parquet is committed."""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb

from .config import DOCS_DATA, State

KEYS = {
    "school_directory": ["ncessch"], "district_directory": ["leaid"], "school_characteristics": ["ncessch"],
    "school_location": ["ncessch"],
    "membership": ["ncessch", "grade", "race", "sex", "total_indicator"],
    "district_membership": ["leaid", "grade", "race", "sex", "total_indicator"],
    "lunch": ["ncessch", "data_group", "lunch_program", "total_indicator"],
    "staff": ["ncessch", "total_indicator"],
    "district_staff": ["leaid", "staff_category", "total_indicator"],
    "district_idea": ["leaid"], "district_el": ["leaid"],
    "legacy_school": ["ncessch"], "legacy_district": ["leaid"],
    "district_finance": ["leaid"],
    "district_graduates": ["leaid", "credential", "race", "sex", "total_indicator"],
    "district_dropout": ["leaid", "grade", "race", "sex", "total_indicator"],
}
EXPAND_DEG = 0.5
MAX_FILE_BYTES = 90 * 1024 * 1024
ROWCOUNTS = DOCS_DATA / "meta" / "rowcounts.json"
DROP_FAIL = 0.20


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def err(self, m: str) -> None:
        self.errors.append(m)

    def warn(self, m: str) -> None:
        self.warnings.append(m)

    def note(self, m: str) -> None:
        self.notes.append(m)

    def print(self) -> None:
        for m in self.notes:
            print("  note:", m)
        for m in self.warnings:
            print("  WARN:", m)
        for m in self.errors:
            print("  FAIL:", m)
        print(f"validate: {len(self.errors)} error(s), {len(self.warnings)} warning(s)")


PSS_KEYS = {"schools": ["row_id"], "enrollment": ["row_id", "dimension", "category"], "teachers": ["row_id", "category"]}


def _collect(c, xs: list[float], ys: list[float]) -> None:
    if isinstance(c[0], (int, float)):
        xs.append(c[0])
        ys.append(c[1])
    else:
        for k in c:
            _collect(k, xs, ys)


def _ipeds_key(family: str) -> list[str] | None:
    from .ipeds_build import load_family_map

    try:
        return load_family_map(family)["key"]
    except SystemExit:
        return None


def _tables(dataset: str) -> dict[str, list[Path]]:
    base = DOCS_DATA / dataset
    return {d.name: sorted(d.glob("*.parquet")) for d in sorted(base.iterdir()) if d.is_dir() and any(d.glob("*.parquet"))}


def current_rowcounts() -> dict[str, dict[str, int]]:
    con = duckdb.connect()
    out: dict[str, dict[str, int]] = {}
    for ds in ("ccd", "pss", "ipeds"):
        if not (DOCS_DATA / ds).exists():
            continue
        for t, files in _tables(ds).items():
            out[f"{ds}.{t}"] = {f.stem: con.execute(f"SELECT count(*) FROM read_parquet('{f.as_posix()}')").fetchone()[0] for f in files}
    return out


def validate(state: State, update_baseline: bool = False) -> Report:
    r = Report()
    con = duckdb.connect()
    rc = current_rowcounts()

    # 1. uniqueness
    for ds in ("ccd", "pss", "ipeds"):
        if not (DOCS_DATA / ds).exists():
            continue
        for t, files in _tables(ds).items():
            keys = KEYS.get(t) if ds == "ccd" else (PSS_KEYS.get(t) if ds == "pss" else _ipeds_key(t))
            if not keys:
                r.warn(f"{ds}.{t}: no uniqueness key defined")
                continue
            for f in files:
                k = ", ".join(f'"{c}"' for c in keys)
                dup = con.execute(f"SELECT count(*) FROM (SELECT {k} FROM read_parquet('{f.as_posix()}') GROUP BY ALL HAVING count(*) > 1)").fetchone()[0]
                if dup:
                    r.err(f"{ds}.{t}/{f.stem}: {dup} duplicate key(s) on ({', '.join(keys)})")

    # 2. file size
    for p in DOCS_DATA.rglob("*.parquet"):
        if p.stat().st_size > MAX_FILE_BYTES:
            r.err(f"{p.relative_to(DOCS_DATA)} is {p.stat().st_size / 1e6:.0f} MB (> 90 MB)")

    # 3. coordinates inside (expanded) state bbox
    w, s, e, n = state.bbox
    for dsname in ("ccd",):
        loc = DOCS_DATA / dsname / "school_location"
        for f in sorted(loc.glob("*.parquet")) if loc.exists() else []:
            bad = con.execute(
                f"SELECT count(*) FROM read_parquet('{f.as_posix()}') WHERE lat IS NOT NULL AND "
                f"(lat < {s - EXPAND_DEG} OR lat > {n + EXPAND_DEG} OR lon < {w - EXPAND_DEG} OR lon > {e + EXPAND_DEG})"
            ).fetchone()[0]
            if bad:
                r.err(f"ccd.school_location/{f.stem}: {bad} coordinate(s) outside the expanded state bbox")

    # 3b. district boundaries: inside the expanded bbox, 7-digit LEA ids
    import json as _json

    for gj in sorted((DOCS_DATA / "geo").glob("districts_*.geojson")):
        doc = _json.loads(gj.read_text(encoding="utf-8"))
        xs: list[float] = []
        ys: list[float] = []

        for f in doc["features"]:
            _collect(f["geometry"]["coordinates"], xs, ys)
            if not re.fullmatch(r"[0-9]{7}", str(f["properties"]["leaid"])):
                r.err(f"{gj.name}: bad leaid {f['properties']['leaid']!r}")
        if xs and (min(xs) < w - EXPAND_DEG or max(xs) > e + EXPAND_DEG or min(ys) < s - EXPAND_DEG or max(ys) > n + EXPAND_DEG):
            r.err(f"{gj.name}: geometry outside the expanded state bbox")

    # 4. membership reconciliation: school-level unit totals vs district-level unit totals (same year)
    mem, dmem = DOCS_DATA / "ccd" / "membership", DOCS_DATA / "ccd" / "district_membership"
    if mem.exists() and dmem.exists():
        for f in sorted(mem.glob("*.parquet")):
            df = dmem / f.name
            if not df.exists():
                continue
            row = con.execute(f"""
              WITH s AS (SELECT leaid, sum(student_count) c FROM read_parquet('{f.as_posix()}')
                         WHERE total_indicator = 'Education Unit Total' GROUP BY 1),
                   d AS (SELECT leaid, sum(student_count) c FROM read_parquet('{df.as_posix()}')
                         WHERE total_indicator = 'Education Unit Total' GROUP BY 1)
              SELECT (SELECT sum(c) FROM s), (SELECT sum(c) FROM d),
                     (SELECT count(*) FROM s JOIN d USING (leaid) WHERE abs(s.c - d.c) > greatest(5, 0.02 * d.c))""").fetchone()
            sc, dc, off = row
            if sc and dc:
                diff = abs(sc - dc) / dc
                msg = f"membership {f.stem}: school sum {sc:,} vs district sum {dc:,} ({diff:.2%}); {off} LEA(s) differ by >2%"
                (r.warn if diff > 0.02 else r.note)(msg)

    # 5. year-over-year enrollment swings (report only)
    if mem.exists():
        files = ", ".join(f"'{f.as_posix()}'" for f in sorted(mem.glob("*.parquet")))
        rows = con.execute(f"""
          WITH t AS (SELECT year, ncessch, student_count c FROM read_parquet([{files}], union_by_name=true)
                     WHERE total_indicator = 'Education Unit Total' AND student_count IS NOT NULL),
               j AS (SELECT a.year, a.ncessch, a.c cur, b.c prev FROM t a JOIN t b ON a.ncessch = b.ncessch AND a.year = b.year + 1)
          SELECT year, count(*) FILTER (WHERE prev >= 50 AND (cur > prev * 1.5 OR cur < prev * 0.5)) swings, count(*) total
          FROM j GROUP BY 1 ORDER BY 1""").fetchall()
        for y, sw, tot in rows:
            if sw:
                r.note(f"enrollment swing >50% (schools with >=50 prior students): {sw} of {tot} in {y}")

    # 6. dictionary completeness
    dic = DOCS_DATA / "meta" / "dictionary.parquet"
    if not dic.exists():
        r.err("meta/dictionary.parquet missing")
    else:
        have = {(a, b, c) for a, b, c in con.execute(f"SELECT dataset, \"table\", \"column\" FROM read_parquet('{dic.as_posix()}')").fetchall()}
        for ds in ("ccd", "pss", "ipeds"):
            if not (DOCS_DATA / ds).exists():
                continue
            for t, files in _tables(ds).items():
                cols = set()
                for f in files:
                    cols |= {x[0] for x in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{f.as_posix()}')").fetchall()}
                missing = sorted(c for c in cols if (ds, t, c) not in have)
                if missing:
                    r.err(f"{ds}.{t}: {len(missing)} column(s) without a dictionary entry: {missing[:6]}")

    # 7. no state literal in meta (except state.json), data paths, or the dictionary
    lits = {state.name.lower(), state.abbrev.lower()}
    for p in DOCS_DATA.rglob("*"):
        rel = str(p.relative_to(DOCS_DATA)).replace("\\", "/")
        if any(l in rel.lower().replace(".", "/").split("/") for l in lits) and rel != "meta/state.json":
            r.err(f"state literal in output path: {rel}")
    meta = DOCS_DATA / "meta"
    for p in meta.glob("*.json"):
        if p.name != "state.json" and any(l in p.read_text(encoding="utf-8").lower() for l in {state.name.lower()}):
            r.err(f"state name appears in meta/{p.name}")
    if dic.exists():
        hit = con.execute(f"SELECT count(*) FROM read_parquet('{dic.as_posix()}') WHERE lower(description || label || caveat) LIKE '%{state.name.lower()}%'").fetchone()[0]
        if hit:
            r.err(f"state name appears in {hit} dictionary row(s)")

    # 8. row counts vs the previous build
    if ROWCOUNTS.exists():
        prev = json.loads(ROWCOUNTS.read_text(encoding="utf-8"))
        for t, years in prev.items():
            for y, n in years.items():
                now = rc.get(t, {}).get(y)
                if now is None:
                    r.err(f"{t}/{y}: present in the previous build but missing now")
                elif n and now < n * (1 - DROP_FAIL):
                    r.err(f"{t}/{y}: row count fell {n} -> {now} (> {DROP_FAIL:.0%} drop)")
    if update_baseline and not r.errors:
        ROWCOUNTS.write_text(json.dumps(rc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return r
