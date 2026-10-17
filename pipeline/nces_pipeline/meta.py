"""Meta outputs: state.json (from config) and years.json (what exists per table)."""
from __future__ import annotations

import json

import duckdb

from .config import DOCS_DATA, State


def write_meta(state: State) -> None:
    meta = DOCS_DATA / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "state.json").write_text(json.dumps(state.state_json(), indent=1) + "\n", encoding="utf-8")
    con = duckdb.connect()
    out: dict = {}
    for ds in ("ccd", "pss", "ipeds"):
        base = DOCS_DATA / ds
        if not base.exists():
            continue
        out[ds] = {}
        for d in sorted(p for p in base.iterdir() if p.is_dir()):
            files = sorted(d.glob("*.parquet"))
            if not files:
                continue
            entry = {}
            for f in files:
                cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{f.as_posix()}')").fetchall()}
                ver = None
                if "data_version" in cols:
                    ver = [r[0] for r in con.execute(f"SELECT DISTINCT data_version FROM read_parquet('{f.as_posix()}') ORDER BY 1").fetchall()]
                entry[f.stem] = ver[0] if ver and len(ver) == 1 else (ver or None)
            out[ds][d.name] = {"years": [int(y) for y in entry], "versions": entry}
    (meta / "years.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
