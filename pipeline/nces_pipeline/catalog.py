"""CCD file catalog from the NCES datatables JSON API."""
from __future__ import annotations

import json

from .config import DATA_RAW, load_sources
from .fetch import client

CATALOG = DATA_RAW / "ccd_catalog.json"
KEEP = ("fileId", "schoolYear", "level", "elementType", "component", "title",
        "version", "size", "fileURL", "fiscal")


def _walk(o, out):
    if isinstance(o, dict):
        if "fileURL" in o:
            out.append(o)
        for v in o.values():
            _walk(v, out)
    elif isinstance(o, list):
        for v in o:
            _walk(v, out)


def build_catalog(refresh: bool = False) -> list[dict]:
    """All CCD files across every school year.

    The API returns 500 for some years unless fiscal (1) and nonfiscal (2) are
    queried separately, so both are queried and merged by fileId.
    """
    if CATALOG.exists() and not refresh:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    base = load_sources()["ccd"]["catalog_api"]
    files: dict[int, dict] = {}
    with client() as c:
        years = c.get(f"{base}/Lookup/").json()["schoolYears"]
        for y in years:
            if not y["id"]:
                continue
            for fiscal in (1, 2):
                r = c.get(f"{base}/File/{fiscal}/0/{y['id']}/0/0/0")
                if r.status_code != 200:
                    continue
                found: list[dict] = []
                _walk(r.json(), found)
                for f in found:
                    if f.get("fileId") is not None:
                        files[f["fileId"]] = {k: f.get(k) for k in KEEP}
    out = sorted(files.values(), key=lambda f: (f["schoolYear"], f["level"], str(f["component"]), f["fileId"]))
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(json.dumps(out, indent=0), encoding="utf-8")
    return out


def year_of(school_year: str) -> int:
    """'2024 - 2025' -> 2024 (fall year)."""
    return int(school_year.split("-")[0].strip())
