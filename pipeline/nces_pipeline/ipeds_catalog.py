"""IPEDS Data Center catalog, scraped from the (ASP.NET postback) Complete Data Files page.

The page lists, for a chosen survey year, every complete data file with its survey, title and links.
We keep only the main data zip and the data-dictionary zip for each file.
"""
from __future__ import annotations

import json
import re

import httpx

from .config import DATA_RAW
from .fetch import UA

PAGE = "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx"
CATALOG = DATA_RAW / "ipeds_catalog.json"
YEAR_FIELD = "ctl00$contentPlaceHolder$ddlYears"
SURVEY_FIELD = "ctl00$contentPlaceHolder$ddlSurveys"


def _hidden(html: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', html):
        t = m.group(0)
        n = re.search(r'name="([^"]*)"', t)
        v = re.search(r'value="([^"]*)"', t)
        if n:
            out[n.group(1)] = v.group(1) if v else ""
    return out


def _clean(x: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip()


def parse_rows(html: str, year: int) -> list[dict]:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.DOTALL):
        links = re.findall(r'href="([^"]*\.zip)"', tr, flags=re.IGNORECASE)
        if not links:
            continue
        cells = [_clean(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.DOTALL)]
        data = next((l for l in links if re.search(r"/[A-Za-z0-9_]+\.zip$", l)
                     and not re.search(r"_(Data_Stata|sps|sas|stata|Dict)\.zip$", l, re.IGNORECASE)), None)
        dic = next((l for l in links if l.lower().endswith("_dict.zip")), None)
        if not data:
            continue
        name = data.rsplit("/", 1)[-1][:-4]
        base = "https://nces.ed.gov"
        rows.append({
            "year": year, "survey": cells[1] if len(cells) > 1 else "", "title": cells[2] if len(cells) > 2 else "",
            "name": name,
            "url": data if data.startswith("http") else base + (data if data.startswith("/") else "/ipeds/datacenter/" + data),
            "dict_url": (dic if dic.startswith("http") else base + (dic if dic.startswith("/") else "/ipeds/datacenter/" + dic)) if dic else None,
        })
    return rows


def build_catalog(refresh: bool = False) -> list[dict]:
    if CATALOG.exists() and not refresh:
        return json.loads(CATALOG.read_text(encoding="utf-8"))
    out: dict[tuple[int, str], dict] = {}
    with httpx.Client(headers=UA, follow_redirects=True, timeout=90) as c:
        html = c.get(PAGE).text
        years = sorted({int(y) for y in re.findall(r'<option[^>]*value="(\d{4})"', html)}, reverse=True)
        base_fields = _hidden(html)
        for y in years:
            d = dict(base_fields)
            d.update({"__EVENTTARGET": YEAR_FIELD, YEAR_FIELD: str(y), SURVEY_FIELD: "-1"})
            r = c.post(PAGE, data=d, headers={"Referer": PAGE})
            r.raise_for_status()
            rows = parse_rows(r.text, y)
            if not rows and y == years[0]:
                rows = parse_rows(html, y)  # the page opens on the newest year; re-selecting it posts nothing new
            for row in rows:
                out.setdefault((row["year"], row["name"]), row)
    rows = sorted(out.values(), key=lambda r: (r["year"], r["name"]))
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    CATALOG.write_text(json.dumps(rows, indent=0), encoding="utf-8", newline="\n")
    return rows
