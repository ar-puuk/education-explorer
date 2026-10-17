"""Repo paths and config loading."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_RAW = ROOT / "data-raw"
# EE_DOCS_DATA redirects all processed output (used for smoke runs of other states without touching docs/data)
DOCS_DATA = Path(os.environ["EE_DOCS_DATA"]) if os.environ.get("EE_DOCS_DATA") else ROOT / "docs" / "data"
MANIFEST = DATA_RAW / "manifest.json"
SCHEMAS = Path(__file__).resolve().parent / "schemas"
SQL_DIR = Path(__file__).resolve().parent / "transform"


@dataclass(frozen=True)
class State:
    name: str
    abbrev: str
    fips: str
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    zoom: float
    site_title: str
    overrides: dict = field(default_factory=dict)

    def state_json(self) -> dict:
        return {
            "name": self.name,
            "abbrev": self.abbrev,
            "fips": self.fips,
            "bbox": list(self.bbox),
            "center": list(self.center),
            "zoom": self.zoom,
            "site_title": self.site_title,
        }


def load_state(key: str) -> State:
    path = CONFIG_DIR / "states" / f"{key}.yml"
    if not path.exists():
        raise SystemExit(f"No state config at {path}")
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    return State(
        name=d["name"],
        abbrev=d["abbrev"],
        fips=str(d["fips"]).zfill(2),
        bbox=tuple(d["bbox"]),
        center=tuple(d["center"]),
        zoom=d["zoom"],
        site_title=d["site_title"],
        overrides=d.get("overrides") or {},
    )


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_sources() -> dict:
    return load_yaml(CONFIG_DIR / "sources.yml")
