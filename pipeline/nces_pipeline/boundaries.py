"""School district boundaries from Census TIGER/Line (UNSD, ELSD, SCSD), simplified to GeoJSON per school year.

TIGER<Y> boundaries are those in effect for the (Y-1)-Y school year, so TIGER2024 is the fall-2023 (2023-24)
vintage. Years without a vintage (the newest school year) reuse the previous one in the app.
"""
from __future__ import annotations

import json

import duckdb

from .config import DATA_RAW, DOCS_DATA, State
from .fetch import client, download, unzip

TYPES = {"UNSD": "unified", "ELSD": "elementary", "SCSD": "secondary"}
FIRST_TIGER, LAST_TIGER = 2011, 2025
SIMPLIFY_DEG = 0.0008  # ~90 m: plenty for a district outline at state scale
PRECISION = 5


def tiger_url(year: int, kind: str, fips: str) -> str:
    return f"https://www2.census.gov/geo/tiger/TIGER{year}/{kind}/tl_{year}_{fips}_{kind.lower()}.zip"


def fetch_boundaries(state: State) -> int:
    n = 0
    with client() as c:
        for y in range(FIRST_TIGER, LAST_TIGER + 1):
            for kind in TYPES:
                p = download(tiger_url(y, kind, state.fips), f"tiger/{y}/{kind.lower()}_{state.fips}.zip", source="census-tiger",
                             release=f"TIGER{y}", c=c, skip_missing=True)
                n += p is not None
    return n


def _round(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], PRECISION), round(coords[1], PRECISION)]
    return [_round(c) for c in coords]


def build_boundaries(state: State) -> list[dict]:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    out_dir = DOCS_DATA / "geo"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for y in range(FIRST_TIGER, LAST_TIGER + 1):
        feats = []
        for kind, label in TYPES.items():
            z = DATA_RAW / "tiger" / str(y) / f"{kind.lower()}_{state.fips}.zip"
            if not z.exists():
                continue
            folder = unzip(z)
            shp = next(iter(folder.rglob("*.shp")), None)
            if shp is None:
                continue
            cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM ST_Read('{shp.as_posix()}')").fetchall()]
            name_col = "NAME" if "NAME" in cols else "NAMELSAD"
            lo = "LOGRADE" if "LOGRADE" in cols else None
            hi = "HIGRADE" if "HIGRADE" in cols else None
            rows = con.execute(f"""
              SELECT GEOID, {name_col}, {lo or 'NULL'}, {hi or 'NULL'},
                     ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, {SIMPLIFY_DEG}))
              FROM ST_Read('{shp.as_posix()}') ORDER BY GEOID""").fetchall()
            for geoid, name, glo, ghi, gj in rows:
                g = json.loads(gj)
                g["coordinates"] = _round(g["coordinates"])
                feats.append({"type": "Feature", "properties": {"leaid": geoid, "name": name, "type": label, "gradeLow": glo, "gradeHigh": ghi},
                              "geometry": g})
        if not feats:
            continue
        fall_year = y - 1
        doc = {"type": "FeatureCollection", "vintage": f"TIGER{y}", "schoolYear": f"{fall_year}-{y % 100:02d}", "features": feats}
        p = out_dir / f"districts_{fall_year}.geojson"
        text = json.dumps(doc, separators=(",", ":")) + "\n"
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8", newline="\n")
        report.append({"year": fall_year, "districts": len(feats), "bytes": len(text)})
        print(f"  districts_{fall_year}.geojson: {len(feats)} districts, {len(text) / 1e3:.0f} KB")
    return report


def vintages() -> list[int]:
    return sorted(int(p.stem.split("_")[1]) for p in (DOCS_DATA / "geo").glob("districts_*.geojson"))
