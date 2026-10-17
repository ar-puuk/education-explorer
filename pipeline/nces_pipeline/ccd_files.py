"""Select and fetch CCD data files from the catalog."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import yaml

from .catalog import build_catalog, year_of
from .config import CONFIG_DIR
from .fetch import client, download, unzip

# Component keys used in schema file names. Catalog component strings are
# normalized to these; anything unmapped is listed by `fetch --check-only`.
COMPONENTS = {
    "directory": "directory",
    "membership": "membership",
    "staff": "staff",
    "lunch program eligibility": "lunch",
    "school characteristics": "characteristics",
    "children with disabilities": "idea",
    "english learners": "el",
}
LEVELS = {"School": "sch", "District": "lea"}  # state (SEA) files are not used: totals come from LEA files

_SKIP = re.compile(r"(sas7bdat|_sas|sas\.zip|_sps|spss|_xlsx|xlsx|\.sps|\.sas|stata|read_|_dict|edge_geoids)", re.IGNORECASE)


@dataclass(frozen=True)
class CcdFile:
    year: int
    school_year: str
    level: str          # sch | lea | sea
    component: str      # directory | membership | ...
    version: str
    url: str
    fiscal: bool
    size: str

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[-1]

    @property
    def rel(self) -> str:
        return f"ccd/{self.year}/{self.level}_{self.component}_{self.filename}"


def _component(f: dict) -> str | None:
    comp = (f.get("component") or "").strip().lower()
    title = (f.get("title") or "").lower()
    if comp in COMPONENTS:
        return COMPONENTS[comp]
    if f.get("fiscal"):
        return "finance_f33" if "f-33" in title or "finance" in title else None
    if "dropout" in title or "dropout" in str(f.get("version", "")).lower():
        return "dropout"
    if "graduate" in title or "graduate" in str(f.get("version", "")).lower():
        return "graduates"
    return None


def _extras() -> list[dict]:
    p = CONFIG_DIR / "ccd_extra_files.yml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or []) if p.exists() else []


def select(min_year: int = 0, max_year: int = 9999, components: set[str] | None = None) -> list[CcdFile]:
    out: dict[tuple, CcdFile] = {}
    for f in build_catalog():
        if f["elementType"] != "Data File" or f["level"] not in LEVELS:
            continue
        url = urljoin("https://nces.ed.gov/ccd/", f["fileURL"])
        if _SKIP.search(url) or not url.lower().endswith((".zip", ".txt", ".csv")):
            continue
        y = year_of(f["schoolYear"])
        if not (min_year <= y <= max_year):
            continue
        comp = _component(f)
        if comp is None or (components and comp not in components):
            continue
        cf = CcdFile(y, f["schoolYear"], LEVELS[f["level"]], comp, str(f.get("version")), url,
                     bool(f.get("fiscal")), str(f.get("size")))
        # multiple versions (e.g. 1a vs 2a revised): keep the last listed (catalog is sorted by fileId)
        out[(y, cf.level, comp, f.get("title") if comp in ("dropout", "graduates") else "")] = cf
    for e in _extras():
        y = year_of(e["school_year"])
        comp = e["component"]
        if not (min_year <= y <= max_year) or (components and comp not in components):
            continue
        cf = CcdFile(y, e["school_year"], LEVELS[e["level"]], comp, str(e.get("version")), e["url"], True, "?")
        out.setdefault((y, cf.level, comp, ""), cf)
    return sorted(out.values(), key=lambda c: (c.year, c.level, c.component))


def fetch_all(files: list[CcdFile]) -> dict[CcdFile, Path]:
    got = {}
    with client() as c:
        for cf in files:
            p = download(cf.url, cf.rel, source="ccd", release=cf.version, c=c, skip_missing=True)
            if p is None:
                print(f"MISSING (404): {cf.url}")
                continue
            got[cf] = p
    return got


def extracted_data_file(zip_or_file: Path) -> Path:
    """Return the CSV/TXT data file inside a downloaded CCD zip (or the file itself).

    Some releases nest a CSV zip next to a SAS zip; the CSV one is followed.
    """
    if zip_or_file.suffix.lower() != ".zip":
        return zip_or_file
    folder = unzip(zip_or_file)
    cands = [p for p in folder.rglob("*")
             if p.is_file() and p.suffix.lower() in (".csv", ".txt", ".dat") and ".utf8" not in p.name]
    if cands:
        return max(cands, key=lambda p: p.stat().st_size)
    nested = [p for p in folder.rglob("*.zip") if "sas" not in p.name.lower()]
    if len(nested) == 1:
        return extracted_data_file(nested[0])
    raise SystemExit(f"no csv/txt inside {zip_or_file} (found: {[p.name for p in folder.rglob('*')]})")
