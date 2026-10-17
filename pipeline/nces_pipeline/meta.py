"""Meta outputs: state.json (from config) and years.json (what exists per table)."""
from __future__ import annotations

import json

import duckdb

from .config import DOCS_DATA, State

CCD_TITLES = {
    "school_directory": "School directory", "district_directory": "District directory",
    "school_characteristics": "School characteristics", "school_location": "School locations (EDGE)",
    "membership": "School membership (enrollment)", "district_membership": "District membership (enrollment)",
    "lunch": "Free/reduced-price lunch eligibility", "staff": "School staff (FTE)", "district_staff": "District staff (FTE)",
    "district_finance": "District finance (F-33)", "district_graduates": "Graduates and completers, by district",
    "district_dropout": "Dropouts (grades 9-12), by district",
    "district_idea": "Students with disabilities (IDEA), by district", "district_el": "English learners, by district",
}


def _table_info(ds: str, table: str) -> dict:
    if ds == "ccd":
        return {"title": CCD_TITLES.get(table, table)}
    if ds == "pss":
        return {"title": {"schools": "Private schools (PSS) public-use file", "enrollment": "Private school enrollment (long)",
                          "teachers": "Private school teachers (long)"}.get(table, table), "survey": "Private School Universe Survey"}
    if ds == "ipeds":
        from .ipeds_files import select

        fs = [f for f in select() if f.family == table]
        if fs:
            f = max(fs, key=lambda x: x.year)
            return {"title": f.title, "survey": f.survey}
    return {}


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
            out[ds][d.name] = {"years": [int(y) for y in entry], "versions": entry, **_table_info(ds, d.name)}
    from .boundaries import vintages

    out["geo"] = {"districts": {"years": vintages(), "title": "School district boundaries (Census TIGER/Line)"}}
    (meta / "years.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
