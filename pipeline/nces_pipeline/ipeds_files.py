"""Select, fetch and locate IPEDS complete data files (Data Center catalog)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import DATA_RAW
from .fetch import client, download, unzip
from .ipeds_catalog import build_catalog

FIRST_YEAR = 2000  # earlier files (1980-1999) use different layouts and are not yet ingested

# family names that changed spelling over the years
FAMILY_ALIASES = {"fahd": "hd", "sfas": "sfa", "icahd": "hd"}


def family_of(name: str, year: int) -> str:
    """'EF2023A' -> 'efa', 'F2223_F1A' -> 'ff1a', 'GR200_24' -> 'gr200', 'IC2023_AY' -> 'icay'."""
    n = name.lower()
    m = re.search(r"_(\d{2})$", n)  # GR200_24: the year is a trailing _yy
    if m and int(m.group(1)) == year % 100:
        return FAMILY_ALIASES.get(n[: m.start()].replace("_", ""), n[: m.start()].replace("_", ""))
    tokens = [f"{year}", f"{year - 1}", f"{(year - 1) % 100:02d}{year % 100:02d}", f"{year % 100:02d}"]
    for t in sorted(tokens, key=len, reverse=True):
        if t in n:
            n = n.replace(t, "", 1)
            break
    fam = n.replace("_", "")
    return FAMILY_ALIASES.get(fam, fam)


@dataclass(frozen=True)
class IpedsFile:
    year: int
    family: str
    name: str
    survey: str
    title: str
    url: str
    dict_url: str | None

    @property
    def rel(self) -> str:
        return f"ipeds/{self.year}/{self.name.lower()}.zip"

    @property
    def dict_rel(self) -> str:
        return f"ipeds/{self.year}/{self.name.lower()}_dict.zip"


def select(min_year: int = FIRST_YEAR, max_year: int = 9999) -> list[IpedsFile]:
    out: dict[tuple[int, str], IpedsFile] = {}
    for r in build_catalog():
        y = r["year"]
        if not (min_year <= y <= max_year):
            continue
        fam = family_of(r["name"], y)
        key = (y, fam)
        if key in out:
            continue  # same family listed under several surveys (e.g. FLAGS): keep the first
        out[key] = IpedsFile(y, fam, r["name"], r["survey"], r["title"], r["url"], r["dict_url"])
    return sorted(out.values(), key=lambda f: (f.family, f.year))


def fetch_all(files: list[IpedsFile], with_dict: bool = True) -> dict[IpedsFile, Path]:
    got: dict[IpedsFile, Path] = {}
    with client() as c:
        for f in files:
            p = download(f.url, f.rel, source="ipeds", release=str(f.year), c=c, skip_missing=True)
            if p is None:
                print(f"MISSING (404): {f.url}")
                continue
            got[f] = p
            if with_dict and f.dict_url:
                download(f.dict_url, f.dict_rel, source="ipeds-dict", release=str(f.year), c=c, skip_missing=True)
    return got


def data_csv(f: IpedsFile) -> Path:
    """The CSV to use: the revised file (_rv) when the zip has one, else the original."""
    folder = unzip(DATA_RAW / f.rel)
    csvs = [p for p in folder.rglob("*.csv") if ".utf8" not in p.name]
    if not csvs:
        raise SystemExit(f"{f.name}: no csv in zip")
    rv = [p for p in csvs if re.search(r"_rv\.csv$", p.name, re.I)]
    return (rv or csvs)[0]


def data_version(f: IpedsFile) -> str:
    folder = unzip(DATA_RAW / f.rel)
    return "revised" if any(re.search(r"_rv\.csv$", p.name, re.I) for p in folder.rglob("*.csv")) else "provisional"


def dict_xlsx(f: IpedsFile) -> Path | None:
    z = DATA_RAW / f.dict_rel
    if not z.exists():
        return None
    folder = unzip(z)
    xs = list(folder.rglob("*.xlsx")) + list(folder.rglob("*.xls"))
    return xs[0] if xs else None
