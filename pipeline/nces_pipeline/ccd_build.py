"""Build CCD tables (directories, membership, ...) for one state from staged raw files."""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import yaml

from .ccd_files import CcdFile, extracted_data_file, select
from .ccd_topics import TOPICS, Topic, bootstrap
from .config import DOCS_DATA, SCHEMAS, State
from .parquet import write_parquet
from .schema import ColumnMap, SchemaDrift, check_header, load_map, map_path
from .stage import stage

PAD = {"ncessch": 12, "leaid": 7, "schid": 7, "fipst": 2}

FLAG_SQL = """CASE
  WHEN {s} IS NULL THEN NULL
  WHEN TRY_CAST({s} AS DOUBLE) IS NOT NULL AND TRY_CAST({s} AS DOUBLE) >= 0 THEN 'reported'
  WHEN TRY_CAST({s} AS DOUBLE) = -1 OR {s} = 'M' THEN 'missing'
  WHEN TRY_CAST({s} AS DOUBLE) = -2 OR {s} IN ('N', '†') THEN 'not_applicable'
  WHEN TRY_CAST({s} AS DOUBLE) = -3 THEN 'suppressed'
  WHEN TRY_CAST({s} AS DOUBLE) = -9 OR {s} = '‡' THEN 'not_meeting_standards'
  ELSE 'unknown_other' END"""

DMS_SQL = """CASE lower(trim({s}))
  WHEN 'reported' THEN 'reported' WHEN 'derived' THEN 'derived' WHEN 'manual adjustment' THEN 'adjusted'
  WHEN 'missing' THEN 'missing' WHEN 'not reported' THEN 'not_reported' WHEN 'suppressed' THEN 'suppressed'
  WHEN 'not applicable' THEN 'not_applicable' WHEN NULL THEN NULL ELSE 'unknown_other' END"""


def q(c: str) -> str:
    return '"' + c.replace('"', '""') + '"'


def txt(c: str) -> str:
    return f"NULLIF(TRIM({q(c)}), '')"


def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def num_value(s: str, typ: str) -> str:
    return f"CASE WHEN TRY_CAST({s} AS DOUBLE) >= 0 THEN CAST(TRY_CAST({s} AS DOUBLE) AS {typ}) END"


def col_expr(raw: str, spec: dict) -> str:
    t = spec.get("type", "VARCHAR")
    s = txt(raw)
    name = spec["name"]
    if spec.get("recode") == "dms_flag":
        return DMS_SQL.format(s=s)
    if t == "VARCHAR":
        if name in PAD:
            return f"CASE WHEN {s} IS NULL THEN NULL ELSE lpad({s}, {PAD[name]}, '0') END"
        return s
    if t == "DATE":
        return f"CAST(COALESCE(TRY_STRPTIME({s}, '%m/%d/%Y'), TRY_STRPTIME({s}, '%m/%d/%y')) AS DATE)"
    if t == "BOOLEAN":
        return f"CASE upper({s}) WHEN 'Y' THEN TRUE WHEN 'N' THEN FALSE WHEN 'YES' THEN TRUE WHEN 'NO' THEN FALSE END"
    return num_value(s, t)


def canonical_columns(topic: Topic) -> list[tuple[str, str]]:
    """Union of canonical (name, type) across all year maps, in stable order."""
    seen: dict[str, str] = {}
    base = SCHEMAS / "ccd" / topic.name
    for p in sorted(base.glob("*.yml")):
        d = yaml.safe_load(p.read_text(encoding="utf-8"))
        for spec in d["columns"].values():
            if spec.get("ignore") or spec.get("unpivot"):
                continue
            seen.setdefault(spec["name"], spec.get("type", "VARCHAR"))
        for u in d.get("unpivot") or []:
            for k in u:
                if k != "source":
                    seen.setdefault(k, "VARCHAR")
    if topic.kind == "flat":
        for n, t in list(seen.items()):
            if t in ("INTEGER", "BIGINT", "DOUBLE"):
                seen[n + "_flag"] = "VARCHAR"
    if topic.kind == "long":
        seen.setdefault(topic.value, topic.value_type)
        seen.setdefault("value_flag", "VARCHAR")
    order = []
    for n in ("fipst", "state_abbrev", "ncessch", "leaid"):
        if n in seen:
            order.append(n)
    dims = [d for d in topic.dims if d in seen]
    tail = [n for n in (*dims, topic.value, "value_flag") if n and n in seen]
    rest = [n for n in seen if n not in order and n not in tail]
    return [(n, seen[n]) for n in order + rest + tail]


def version_label(cf: CcdFile) -> str:
    v = (cf.version or "").lower()
    m = re.search(r"(\d)a", v) or re.search(r"_(\d)a_", cf.filename.lower())
    if not m:
        return "unknown"
    return {"0": "preliminary", "1": "provisional", "2": "final"}.get(m.group(1), "unknown")


def select_sql(cm: ColumnMap, topic: Topic, staged: Path, cf: CcdFile, canon: list[tuple[str, str]], unp: list[dict]) -> str:
    src = f"read_parquet('{staged.as_posix()}')"
    year = cf.year
    school_year = f"{year}-{(year + 1) % 100:02d}"
    meta = (f"{year}::INTEGER AS year, {sql_str(school_year)} AS school_year, "
            f"{sql_str(version_label(cf))} AS data_version, {sql_str(cf.filename)} AS source_file")
    mapped = {s["name"]: (raw, s) for raw, s in cm.kept.items() if not s.get("unpivot")}

    def sel_for(extra: dict[str, str]) -> str:
        parts = []
        for n, t in canon:
            if n in extra:
                parts.append(f"{extra[n]} AS {q(n)}")
            elif n in mapped:
                raw, s = mapped[n]
                parts.append(f"{col_expr(raw, s)} AS {q(n)}")
            elif n.endswith("_flag") and n[:-5] in mapped and mapped[n[:-5]][1].get("type", "VARCHAR") not in ("VARCHAR", "DATE", "BOOLEAN"):
                raw = mapped[n[:-5]][0]
                parts.append(f"{FLAG_SQL.format(s=txt(raw))} AS {q(n)}")
            else:
                parts.append(f"CAST(NULL AS {t}) AS {q(n)}")
        return ", ".join(parts)

    if topic.kind == "flat":
        return f"SELECT {meta}, {sel_for({})} FROM {src}"
    if not unp:
        return f"SELECT {meta}, {sel_for({})} FROM {src}"
    selects = []
    for u in unp:
        raw = u["source"]
        s = txt(raw)
        extra = {k: sql_str(v) for k, v in u.items() if k != "source"}
        extra[topic.value] = num_value(s, topic.value_type)
        extra["value_flag"] = FLAG_SQL.format(s=s)
        selects.append(f"SELECT {meta}, {sel_for(extra)} FROM {src}")
    return " UNION ALL ".join(selects)


def output_path(topic: Topic, year: int) -> Path:
    return DOCS_DATA / "ccd" / topic.name / f"{year}.parquet"


def raw_files(min_year: int = 0, max_year: int = 9999) -> dict[tuple[int, str], CcdFile]:
    files = {}
    for cf in select(min_year=min_year, max_year=max_year):
        files[(cf.year, f"{cf.level}_{cf.component}")] = cf
    return files


def raw_path_for(cf: CcdFile) -> Path:
    from .config import DATA_RAW

    return extracted_data_file(DATA_RAW / cf.rel)


def build_ccd(state: State, years: list[int] | None = None, topics: list[str] | None = None) -> list[dict]:
    files = raw_files()
    report = []
    con = duckdb.connect()
    for topic in TOPICS.values():
        if topics and topic.name not in topics:
            continue
        canon = None
        for (y, comp), cf in sorted(files.items()):
            if comp != topic.component or (years and y not in years):
                continue
            if not map_path("ccd", topic.name, y).exists():
                raise SchemaDrift(f"No column map for ccd/{topic.name}/{y}. "
                                  f"Run: python -m nces_pipeline build --scaffold-map ccd {topic.name} {y}")
            if canon is None:
                canon = canonical_columns(topic)
            raw = raw_path_for(cf)
            staged = stage(raw, state)
            cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{staged.as_posix()}')").fetchall()]
            cm = load_map("ccd", topic.name, y)
            check_header(cm, cols)
            d = yaml.safe_load(cm.path.read_text(encoding="utf-8"))
            sql = select_sql(cm, topic, staged, cf, canon, d.get("unpivot") or [])
            n = write_parquet(con, sql, output_path(topic, y), list(topic.sort) + ["year"])
            report.append({"table": topic.name, "year": y, "rows": n, "source": cf.filename})
            print(f"  {topic.name} {y}: {n} rows")
    return report


def write_bootstrap_map(topic: Topic, year: int, raw_cols: list[str], force: bool = False) -> Path:
    p = map_path("ccd", topic.name, year)
    if p.exists() and not force:
        return p
    cols, unpivot = bootstrap(topic, year, raw_cols)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"source": "ccd", "topic": topic.name, "year": year, "columns": cols}
    if unpivot:
        doc["unpivot"] = unpivot
    p.write_text(yaml.safe_dump(doc, sort_keys=False, width=140, allow_unicode=True), encoding="utf-8")
    return p
