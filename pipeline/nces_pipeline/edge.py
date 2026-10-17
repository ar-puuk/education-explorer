"""NCES EDGE school locations: coordinates, locale and geography per school-year.

2014-15 comes from the CCD "EDGE_GEOIDS" CSV; 2015-16 onward from EDGE_GEOCODE_PUBLICSCH_<yyyy>
(attribute table read from the shapefile .dbf, or the 2015-16 file geodatabase, through DuckDB spatial,
because the .TXT versions are headerless and their column order changes between years).
"""
from __future__ import annotations

from pathlib import Path

from .config import DATA_RAW, load_sources
from .fetch import client, download, unzip

CCD_BASE = "https://nces.ed.gov/ccd/data/zip"
FIRST, LAST = 2014, 2024


def edge_url(year: int) -> str:
    if year == 2014:
        return f"{CCD_BASE}/EDGE_GEOIDS_201415_PUBLIC_SCHOOL_csv.zip"
    base = load_sources()["edge"]["base"]
    return f"{base}/EDGE_GEOCODE_PUBLICSCH_{year % 100:02d}{(year + 1) % 100:02d}.zip"


def edge_rel(year: int) -> str:
    return f"edge/{year}/{edge_url(year).rsplit('/', 1)[-1]}"


def fetch_edge(check_only: bool = False) -> dict[int, Path]:
    got = {}
    with client() as c:
        for y in range(FIRST, LAST + 1):
            rel = edge_rel(y)
            if check_only:
                print(f"EDGE {y}: {'present' if (DATA_RAW / rel).exists() else 'missing'}")
                continue
            p = download(edge_url(y), rel, source="edge", release=f"{y}-{(y + 1) % 100:02d}", c=c, skip_missing=True)
            if p is None:
                print(f"EDGE {y}: not available (404)")
            else:
                got[y] = p
    return got


def edge_table_source(year: int) -> tuple[str, Path] | None:
    """(kind, path) where kind in csv|dbf|gdb for the extracted EDGE attribute table."""
    z = DATA_RAW / edge_rel(year)
    if not z.exists():
        return None
    folder = unzip(z)
    for nested in folder.rglob("*.zip"):
        unzip(nested)
    csvs = [p for p in folder.rglob("*.csv")]
    if csvs:
        return "csv", csvs[0]
    dbfs = [p for p in folder.rglob("*.dbf")]
    if dbfs:
        return "dbf", dbfs[0]
    gdbs = [p for p in folder.rglob("*.gdb") if p.is_dir()]
    if gdbs:
        return "gdb", gdbs[0]
    raise SystemExit(f"EDGE {year}: no csv/dbf/gdb found in {folder}")


# ---------------------------------------------------------------- map bootstrap + build
import re  # noqa: E402

import duckdb  # noqa: E402
import yaml  # noqa: E402

from .ccd_build import col_expr, q, sql_str  # noqa: E402
from .config import DOCS_DATA, State  # noqa: E402
from .parquet import write_parquet  # noqa: E402
from .rawio import read_sql  # noqa: E402
from .schema import check_header, load_map, map_path  # noqa: E402

EDGE_NAMES = {
    "NCESSCH": ("ncessch", "VARCHAR"), "LEAID": ("leaid", "VARCHAR"), "NAME": ("school_name", "VARCHAR"),
    "FIPST": ("fipst", "VARCHAR"), "STFIP": ("fipst", "VARCHAR"), "OPSTFIPS": ("opstfips", "VARCHAR"),
    "LSTREE": ("street", "VARCHAR"), "STREET": ("street", "VARCHAR"), "LCITY": ("city", "VARCHAR"),
    "CITY": ("city", "VARCHAR"), "LSTATE": ("state", "VARCHAR"), "STATE": ("state", "VARCHAR"),
    "LZIP": ("zip", "VARCHAR"), "ZIP": ("zip", "VARCHAR"), "LZIP4": ("zip4", "VARCHAR"),
    "CONUM": ("county_fips", "VARCHAR"), "CNTY": ("county_fips", "VARCHAR"),
    "CONAME": ("county_name", "VARCHAR"), "NMCNTY": ("county_name", "VARCHAR"),
    "LOCALE": ("locale", "VARCHAR"), "LATCODE": ("lat", "DOUBLE"), "LAT": ("lat", "DOUBLE"),
    "LONGCODE": ("lon", "DOUBLE"), "LON": ("lon", "DOUBLE"),
    "CBSA": ("cbsa", "VARCHAR"), "NMCBSA": ("cbsa_name", "VARCHAR"), "CBSATYPE": ("cbsa_type", "VARCHAR"),
    "CSA": ("csa", "VARCHAR"), "NMCSA": ("csa_name", "VARCHAR"), "NECTA": ("necta", "VARCHAR"),
    "NMNECTA": ("necta_name", "VARCHAR"), "METMIC": ("metmic", "VARCHAR"),
    "CD": ("cd", "VARCHAR"), "SLDL": ("sldl", "VARCHAR"), "SLDU": ("sldu", "VARCHAR"),
}


def edge_bootstrap(cols: list[str]) -> dict:
    out: dict = {}
    for c in cols:
        base = re.sub(r"(1516|15)$", "", c) if c not in EDGE_NAMES else c
        if c in ("SURVYEAR", "SCHOOLYEAR"):
            out[c] = {"ignore": True, "reason": "replaced by derived year/school_year columns"}
        elif base in EDGE_NAMES:
            n, t = EDGE_NAMES[base]
            out[c] = {"name": n, "type": t}
            if n in ("lat", "lon"):
                out[c]["signed"] = True
        else:
            out[c] = {"name": "TODO_" + c.lower(), "type": "VARCHAR", "todo": True}
    return out


def edge_columns(year: int) -> list[str]:
    kind, p = edge_table_source(year)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    pp = p.as_posix()
    if kind == "csv":
        q_ = f"SELECT * FROM {read_sql(p)} LIMIT 0"
    else:
        q_ = f"SELECT * EXCLUDE (OGC_FID) FROM ST_Read('{pp}') LIMIT 0"
    return [r[0] for r in con.execute("DESCRIBE " + q_).fetchall() if r[0].lower() != "geom"]


def write_edge_map(year: int, force: bool = False) -> Path:
    p = map_path("edge", "school_location", year)
    if p.exists() and not force:
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"source": "edge", "topic": "school_location", "year": year, "columns": edge_bootstrap(edge_columns(year))}
    p.write_text(yaml.safe_dump(doc, sort_keys=False, width=140), encoding="utf-8")
    return p


def build_edge(state: State, years: list[int] | None = None) -> list[dict]:
    from .stage import stage_frame

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    report = []
    canon: dict[str, str] = {}
    maps = {}
    for y in range(FIRST, LAST + 1):
        if edge_table_source(y) is None:
            continue
        maps[y] = load_map("edge", "school_location", y)
        for spec in maps[y].kept.values():
            canon.setdefault(spec["name"], spec.get("type", "VARCHAR"))
    for y, cm in maps.items():
        if years and y not in years:
            continue
        kind, p = edge_table_source(y)
        pp = p.as_posix()
        if kind == "csv":
            src = f"SELECT * FROM {read_sql(p)}"
        else:
            src = f"SELECT * EXCLUDE (OGC_FID, geom) FROM ST_Read('{pp}')"
        staged = stage_frame(con, src, f"edge_{y}", state)
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{staged.as_posix()}')").fetchall()]
        check_header(cm, cols)
        by_name = {s["name"]: (raw, s) for raw, s in cm.kept.items()}
        parts = [f"{y}::INTEGER AS year", f"{sql_str(f'{y}-{(y + 1) % 100:02d}')} AS school_year"]
        for n, t in canon.items():
            if n in by_name:
                raw, s = by_name[n]
                parts.append(f"{col_expr(raw, s)} AS {q(n)}")
            else:
                parts.append(f"CAST(NULL AS {t}) AS {q(n)}")
        parts += ["'edge' AS coord_source", "FALSE AS coord_approximate", f"{sql_str(Path(p).name)} AS source_file"]
        sql = f"SELECT {', '.join(parts)} FROM read_parquet('{staged.as_posix()}')"
        n = write_parquet(con, sql, DOCS_DATA / "ccd" / "school_location" / f"{y}.parquet", ["ncessch"])
        report.append({"table": "school_location", "year": y, "rows": n})
        print(f"  school_location {y}: {n} rows")
    return report


def build_carry_forward(state: State) -> list[dict]:
    """Years that have a CCD directory but no EDGE file yet (e.g. a preliminary directory) get
    coordinates carried forward from each school's most recent EDGE record. Schools with no prior
    EDGE record stay without coordinates until geocoded."""
    con = duckdb.connect()
    loc_dir = DOCS_DATA / "ccd" / "school_location"
    dir_dir = DOCS_DATA / "ccd" / "school_directory"
    edge_years = sorted(p for p in loc_dir.glob("*.parquet") if int(p.stem) <= LAST)
    report = []
    for dp in sorted(dir_dir.glob("*.parquet")):
        y = int(dp.stem)
        if y <= LAST:
            continue
        prev = ", ".join(f"'{p.as_posix()}'" for p in edge_years)
        cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{edge_years[0].as_posix()}')").fetchall()]
        names = [c for c in cols if c not in ("year", "school_year", "coord_source", "coord_approximate", "source_file")]
        sel = ", ".join(f"l.{q(c)}" for c in names if c != "ncessch")
        sql = f"""
          SELECT {y}::INTEGER AS year, '{y}-{(y + 1) % 100:02d}' AS school_year, d.ncessch AS ncessch, {sel},
                 'edge_prior_year' AS coord_source, FALSE AS coord_approximate, l.source_file AS source_file
          FROM read_parquet('{dp.as_posix()}') d
          JOIN (SELECT * FROM read_parquet([{prev}], union_by_name=true)
                QUALIFY row_number() OVER (PARTITION BY ncessch ORDER BY year DESC) = 1) l USING (ncessch)"""
        # column order must match the EDGE tables: build from the first table's column order
        order = ["year", "school_year"] + names + ["coord_source", "coord_approximate", "source_file"]
        sql = f"SELECT {', '.join(q(c) for c in order)} FROM ({sql})"
        n = write_parquet(con, sql, loc_dir / f"{y}.parquet", ["ncessch"])
        report.append({"table": "school_location", "year": y, "rows": n})
        print(f"  school_location {y}: {n} rows (coordinates carried forward from earlier EDGE years)")
    return report
