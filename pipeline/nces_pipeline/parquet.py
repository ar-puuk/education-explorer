"""Deterministic Parquet writing."""
from __future__ import annotations

from pathlib import Path

import duckdb

ROW_GROUP_SIZE = 122880


def write_parquet(con: duckdb.DuckDBPyConnection, select_sql: str, dest: Path, order_by: list[str]) -> int:
    """Write `select_sql` ordered by `order_by` as ZSTD Parquet. Returns row count.

    Deterministic: explicit ORDER BY, single writer thread, fixed compression and row-group size,
    no timestamps in the data. Unchanged inputs give byte-identical output.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".parquet.tmp")
    order = ", ".join(order_by)
    con.execute("SET threads=1")
    con.execute("SET preserve_insertion_order=true")
    d = str(tmp).replace("\\", "/").replace("'", "''")
    con.execute(
        f"COPY (SELECT * FROM ({select_sql}) ORDER BY {order}) TO '{d}' "
        f"(FORMAT PARQUET, COMPRESSION ZSTD, COMPRESSION_LEVEL 9, ROW_GROUP_SIZE {ROW_GROUP_SIZE})"
    )
    n = con.execute(f"SELECT count(*) FROM read_parquet('{d}')").fetchone()[0]
    if dest.exists() and dest.read_bytes() == tmp.read_bytes():
        tmp.unlink()
    else:
        tmp.replace(dest)
    return n
