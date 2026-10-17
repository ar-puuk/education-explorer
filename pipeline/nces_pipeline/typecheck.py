"""Shared type-drift guard: typed columns must not silently lose values."""
from __future__ import annotations

from pathlib import Path

import duckdb

from .schema import SchemaDrift


def check_casts(con: duckdb.DuckDBPyConnection, parquet: Path, cols: list[tuple[str, str]], label: str, hint: str) -> None:
    """cols = (raw column in the staged parquet, SQL type). Raises SchemaDrift when a non-empty value cannot be
    cast to its mapped type (for example text codes in a column the map says is numeric)."""
    checks: list[str] = []
    names: list[str] = []
    for raw, typ in cols:
        if typ == "VARCHAR":
            continue
        v = f"NULLIF(TRIM(\"{raw}\"), '')"
        # sentinel text codes that the build deliberately turns into NULL + flag are not "losses"
        checks.append(f"count(*) FILTER (WHERE {v} IS NOT NULL AND {v} NOT IN ('M', 'N', '†', '‡') "
                      f"AND TRY_CAST({v} AS {typ}) IS NULL)")
        names.append(raw)
    if not checks:
        return
    row = con.execute(f"SELECT {', '.join(checks)} FROM read_parquet('{parquet.as_posix()}')").fetchone()
    bad = [f"{n} ({c} values)" for n, c in zip(names, row) if c]
    if bad:
        raise SchemaDrift(f"TYPE DRIFT in {label}: values cannot be cast to the mapped type: {', '.join(bad[:8])}. {hint}")
