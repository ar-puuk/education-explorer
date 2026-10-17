"""Per-source/topic/year column maps and the schema-drift guard.

A map file lives at schemas/<source>/<topic>/<year>.yml:

    topic: school_directory
    year: 2024
    columns:
      SCHOOL_YEAR: {name: school_year, type: VARCHAR}
      LEAID:       {name: leaid, type: VARCHAR}
      SOME_COL:    {ignore: true, reason: "why"}

Every raw column must appear in `columns`; a raw header column not in the map,
or a mapped column absent from the raw header, fails the build.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import SCHEMAS

TYPES = {"VARCHAR", "INTEGER", "BIGINT", "DOUBLE", "DATE", "BOOLEAN"}


class SchemaDrift(SystemExit):
    pass


@dataclass
class ColumnMap:
    source: str
    topic: str
    year: int
    columns: dict[str, dict]
    path: Path

    @property
    def kept(self) -> dict[str, dict]:
        return {k: v for k, v in self.columns.items() if not v.get("ignore")}


def map_path(source: str, topic: str, year: int) -> Path:
    return SCHEMAS / source / topic / f"{year}.yml"


def load_map(source: str, topic: str, year: int) -> ColumnMap:
    p = map_path(source, topic, year)
    if not p.exists():
        raise SchemaDrift(
            f"No column map for {source}/{topic}/{year} at {p}.\n"
            f"Run: python -m nces_pipeline build --scaffold-map {source} {topic} {year}"
        )
    d = yaml.safe_load(p.read_text(encoding="utf-8"))
    for src, spec in d["columns"].items():
        if spec.get("unpivot"):
            continue
        if spec.get("ignore"):
            if not spec.get("reason"):
                raise SchemaDrift(f"{p}: ignored column {src} needs a reason")
            continue
        if spec.get("type", "VARCHAR") not in TYPES:
            raise SchemaDrift(f"{p}: column {src} has unknown type {spec.get('type')}")
        if "name" not in spec:
            raise SchemaDrift(f"{p}: column {src} needs a name")
    return ColumnMap(source, topic, year, d["columns"], p)


def check_header(cm: ColumnMap, raw_cols: list[str]) -> None:
    """Fail loudly on unmapped or missing columns."""
    raw = set(raw_cols)
    mapped = set(cm.columns)
    new = [c for c in raw_cols if c not in mapped]
    gone = [c for c in cm.columns if c not in raw]
    if not new and not gone:
        return
    lines = [f"SCHEMA DRIFT in {cm.source}/{cm.topic}/{cm.year} (map: {cm.path})"]
    if new:
        lines.append(f"  {len(new)} raw column(s) NOT in the map:")
        for c in new:
            near = difflib.get_close_matches(c, list(gone) or list(mapped), n=2, cutoff=0.5)
            lines.append(f"    + {c}" + (f"   (nearest known: {', '.join(near)})" if near else ""))
    if gone:
        lines.append(f"  {len(gone)} mapped column(s) MISSING from the raw file:")
        for c in gone:
            near = difflib.get_close_matches(c, new, n=2, cutoff=0.5)
            lines.append(f"    - {c}" + (f"   (maybe renamed to: {', '.join(near)})" if near else ""))
    lines.append("Edit the YAML map (add/rename/ignore the columns above) and re-run.")
    raise SchemaDrift("\n".join(lines))


def scaffold(source: str, topic: str, year: int, raw_cols: list[str]) -> Path:
    """Create a map for `year` from the nearest earlier year's map; mark differences with TODO."""
    base = SCHEMAS / source / topic
    base.mkdir(parents=True, exist_ok=True)
    prev = sorted(int(p.stem) for p in base.glob("*.yml") if int(p.stem) < year)
    cols: dict[str, dict] = {}
    if prev:
        old = yaml.safe_load((base / f"{prev[-1]}.yml").read_text(encoding="utf-8"))["columns"]
    else:
        old = {}
    for c in raw_cols:
        cols[c] = dict(old[c]) if c in old else {"name": "TODO_" + c.lower(), "type": "VARCHAR", "todo": True}
    gone = [c for c in old if c not in raw_cols]
    p = map_path(source, topic, year)
    header = (f"# Scaffolded from {prev[-1] if prev else 'nothing'}. Resolve every `todo` and verify types.\n"
              + (f"# Columns in the previous map but absent from this file: {', '.join(gone)}\n" if gone else ""))
    p.write_text(header + yaml.safe_dump({"source": source, "topic": topic, "year": year, "columns": cols},
                                         sort_keys=False, width=120), encoding="utf-8", newline="\n")
    return p
