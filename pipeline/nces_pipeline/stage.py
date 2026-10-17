"""Stage: reduce a (possibly multi-GB, national) raw file to one state's rows, as VARCHAR Parquet.

Staged files live under data-raw/_stage/<state>/ (gitignored) and are keyed by the raw
file's manifest hash, so a changed raw file restages automatically.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb

from .config import DATA_RAW, State
from .rawio import header_of, read_sql

# Raw column that carries the state, tried in order. The value is compared as text.
STATE_COLUMNS = [("FIPST", "fips"), ("FIPS", "fips"), ("STATE_FIPS", "fips"), ("STABR", "abbrev"),
                 ("ST", "abbrev"), ("STABBR", "abbrev"), ("PSTABB", "abbrev"), ("PSTANSI", "fips"),
                 ("STFIP", "fips"), ("STFIP15", "fips"), ("OPSTFIPS", "fips"), ("LSTATE", "abbrev"),
                 ("STATE", "abbrev")]


def state_filter(cols: list[str], state: State, override: tuple[str, str] | None = None) -> str:
    present = {c.upper(): c for c in cols}
    pairs = [override] if override else STATE_COLUMNS
    for col, kind in pairs:
        if col in present:
            raw = present[col]
            if kind == "fips":
                return f"lpad(trim(\"{raw}\"), 2, '0') = '{state.fips}'"
            return f"upper(trim(\"{raw}\")) = '{state.abbrev.upper()}'"
    raise SystemExit(f"no state column found among {cols[:30]}...")


def staged_path(raw: Path, state: State) -> Path:
    key = hashlib.sha1(f"{raw.resolve()}|{raw.stat().st_size}|{raw.stat().st_mtime_ns}".encode()).hexdigest()[:10]
    return DATA_RAW / "_stage" / state.abbrev.lower() / f"{raw.stem}.{key}.parquet"


def stage(raw: Path, state: State, override: tuple[str, str] | None = None) -> Path:
    dest = staged_path(raw, state)
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    for old in dest.parent.glob(f"{raw.stem}.*.parquet"):
        old.unlink()
    con = duckdb.connect()
    src = read_sql(raw)
    cols = header_of(raw)
    where = state_filter(cols, state, override)
    tmp = dest.with_suffix(".tmp")
    t = str(tmp).replace("\\", "/")
    con.execute(f"COPY (SELECT * FROM {src} WHERE {where}) TO '{t}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    tmp.replace(dest)
    return dest


def stage_frame(con: duckdb.DuckDBPyConnection, select_sql: str, name: str, state: State,
                override: tuple[str, str] | None = None) -> Path:
    """Stage an arbitrary SELECT (e.g. an ST_Read of a dbf/gdb) as VARCHAR Parquet filtered to the state."""
    dest = DATA_RAW / "_stage" / state.abbrev.lower() / f"{name}.parquet"
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    cols = [r[0] for r in con.execute(f"DESCRIBE {select_sql}").fetchall()]
    where = state_filter(cols, state, override)
    casted = ", ".join(f'CAST("{c}" AS VARCHAR) AS "{c}"' for c in cols)
    tmp = dest.with_suffix(".tmp")
    con.execute(f"COPY (SELECT {casted} FROM ({select_sql}) WHERE {where}) TO '{tmp.as_posix()}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    tmp.replace(dest)
    return dest
