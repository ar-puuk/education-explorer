"""CCD universe files before 2014-15 ("legacy" layouts): school and district files, 1997-98 to 2013-14.

All are read from the SAS7BDAT versions (one reader for every year; they also carry variable labels),
filtered to the state, and kept as wide tables with every column as published (names lower-cased, the survey-year
suffix removed: SCHNAM98 -> schnam). Membership is also derived to a long table.
Years before 1997-98 only exist as fixed-width text and are not ingested.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import duckdb
import pyreadstat

from .catalog import build_catalog, year_of
from .config import DATA_RAW, State
from .fetch import client, download, unzip

FIRST_LEGACY, LAST_LEGACY = 1997, 2013
_NOT_DATA = re.compile(r"(_dat|_txt|^SAS_|^SPSS_|^Read|sascode|spsscode|xls|_sps|dr\d|^dr|agdr|drp|ccdagn|sdf|sd2_|stfis|^st\d)", re.IGNORECASE)
_SCHOOL = re.compile(r"^(psu|sc\d)", re.IGNORECASE)
_DISTRICT = re.compile(r"^(pau|ag\d)", re.IGNORECASE)
CHUNK = 20000

STATE_COLS = ["FIPST", "STATE", "FIPS", "STABR", "LSTATE", "MSTATE"]


@dataclass(frozen=True)
class LegacyFile:
    year: int
    level: str  # school | district
    url: str

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[-1]

    @property
    def rel(self) -> str:
        return f"ccd/{self.year}/legacy_{self.level}_{self.filename}"


def legacy_files(level: str | None = None) -> list[LegacyFile]:
    out: dict[tuple, LegacyFile] = {}
    for f in build_catalog():
        if f["elementType"] != "Data File" or f.get("fiscal") or f["level"] not in ("School", "District"):
            continue
        y = year_of(f["schoolYear"])
        if not (FIRST_LEGACY <= y <= LAST_LEGACY):
            continue
        url = urljoin("https://nces.ed.gov/ccd/", f["fileURL"])
        name = url.rsplit("/", 1)[-1]
        lv = "school" if f["level"] == "School" else "district"
        if level and lv != level:
            continue
        if not url.lower().endswith(".zip") or _NOT_DATA.search(name):
            continue
        if not (_SCHOOL if lv == "school" else _DISTRICT).search(name):
            continue
        out[(y, lv, name.lower())] = LegacyFile(y, lv, url)
    return sorted(out.values(), key=lambda f: (f.level, f.year, f.filename))


def fetch_legacy() -> int:
    n = 0
    with client() as c:
        for f in legacy_files():
            p = download(f.url, f.rel, source="ccd", release="legacy", c=c, skip_missing=True)
            n += p is not None
    return n


def sas_in(f: LegacyFile) -> Path | None:
    folder = unzip(DATA_RAW / f.rel)
    fs = [p for p in folder.rglob("*") if p.suffix.lower() == ".sas7bdat"]
    return fs[0] if fs else None


def _fmt(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float):
        if math.isnan(v):
            return None
        return str(int(v)) if v == int(v) else repr(v)
    s = str(v).strip()
    return s or None


def _is_state(row_val, state: State) -> bool:
    if row_val is None or (isinstance(row_val, float) and math.isnan(row_val)):
        return False
    if isinstance(row_val, str):
        s = row_val.strip()
        if s.isdigit():
            return int(s) == int(state.fips)
        return s.upper() == state.abbrev.upper()
    try:
        return int(row_val) == int(state.fips)
    except (TypeError, ValueError):
        return False


def stage_legacy(year: int, level: str, state: State) -> Path | None:
    """State rows of every chunk file for (year, level) as one VARCHAR Parquet (+ labels sidecar)."""
    files = [f for f in legacy_files(level) if f.year == year]
    srcs = [(f, sas_in(f)) for f in files if (DATA_RAW / f.rel).exists()]
    srcs = [(f, s) for f, s in srcs if s is not None]
    if not srcs:
        return None
    dest = DATA_RAW / "_stage" / state.abbrev.lower() / f"ccdlegacy_{level}_{year}.parquet"
    sig = "|".join(f"{s.name}:{s.stat().st_size}" for _, s in srcs)
    stamp = dest.with_suffix(".stamp")
    if dest.exists() and stamp.exists() and stamp.read_text() == sig:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    created = False
    labels: dict[str, str] = {}
    cols: list[str] = []
    for _, src in srcs:
        _, meta = pyreadstat.read_sas7bdat(str(src), metadataonly=True, output_format="dict")
        cols_f = [c.upper() for c in meta.column_names]
        labels.update({c: (l or "") for c, l in zip(cols_f, meta.column_labels) if l})
        scol = next((c for c in STATE_COLS if c in cols_f), None)
        if scol is None:
            raise SystemExit(f"{src.name}: no state column among {STATE_COLS}")
        if not created:
            cols = cols_f
            con.execute("CREATE TABLE t(" + ", ".join(f'"{c}" VARCHAR' for c in cols) + ")")
            created = True
        elif cols_f != cols:
            # chunk files of one release share a layout; tolerate extras by NULL-filling/ignoring
            missing = [c for c in cols_f if c not in cols]
            if missing:
                raise SystemExit(f"{src.name}: columns differ between chunk files: {missing[:5]}")
        offset = 0
        while True:
            data, _m = pyreadstat.read_sas7bdat(str(src), output_format="dict", row_limit=CHUNK, row_offset=offset)
            if not data:
                break
            names = list(data)
            n = len(data[names[0]])
            if n == 0:
                break
            sc_name = next(k for k in names if k.upper() == scol)
            keep = [i for i in range(n) if _is_state(data[sc_name][i], state)]
            if keep:
                order = [next(k for k in names if k.upper() == c) if any(k.upper() == c for k in names) else None for c in cols]
                rows = [[_fmt(data[k][i]) if k else None for k in order] for i in keep]
                con.executemany(f"INSERT INTO t VALUES ({', '.join(['?'] * len(cols))})", rows)
            offset += CHUNK
            if n < CHUNK:
                break
    tmp = dest.with_suffix(".tmp")
    con.execute(f"COPY (SELECT * FROM t) TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    tmp.replace(dest)
    dest.with_suffix(".labels.json").write_text(json.dumps(labels), encoding="utf-8", newline="\n")
    stamp.write_text(sig)
    return dest
