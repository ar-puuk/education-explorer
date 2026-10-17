"""Reading raw delimited files through DuckDB (everything as VARCHAR first)."""
from __future__ import annotations

import codecs
from pathlib import Path

import duckdb


def _opts(delim: str | None, header: bool = True) -> str:
    parts = ["all_varchar=true", "sample_size=20000", "ignore_errors=false",
             "strict_mode=false", "null_padding=true", f"header={'true' if header else 'false'}"]
    if delim:
        parts.append(f"delim='{delim}'")
    return ", ".join(parts)


def detect(path: Path) -> tuple[str, Path]:
    """Return (delimiter, utf-8 readable path)."""
    with path.open("rb") as f:
        head = f.read(200_000)
    first = head.split(b"\n", 1)[0].decode("latin-1")
    if first.count("\t") >= 2:
        delim = "\t"
    elif first.count("|") >= 2 and first.count(",") < first.count("|"):
        delim = "|"
    else:
        delim = ","
    return delim, ensure_utf8(path)


def ensure_utf8(path: Path) -> Path:
    """Return path if it is valid UTF-8, else a cp1252->UTF-8 transcoded copy next to it.

    (DuckDB's latin-1 reader rejects cp1252-only bytes such as curly quotes.)
    """
    dec = codecs.getincrementaldecoder("utf-8")()
    try:
        with path.open("rb") as f:
            while chunk := f.read(64 << 20):
                dec.decode(chunk)
            dec.decode(b"", final=True)
        return path
    except UnicodeDecodeError:
        pass
    out = path.with_name(path.stem + ".utf8" + path.suffix)
    if not out.exists():
        tmp = out.with_suffix(out.suffix + ".part")
        with path.open("rb") as src, tmp.open("wb") as dst:
            for line in src:
                dst.write(line.decode("cp1252", errors="replace").encode("utf-8"))
        tmp.replace(out)
    return out


def read_sql(path: Path, delim: str | None = None, header: bool = True) -> str:
    d, readable = detect(path)
    delim = delim or d
    p = str(readable).replace("\\", "/").replace("'", "''")
    return f"read_csv('{p}', {_opts(delim, header)})"


def header_of(path: Path) -> list[str]:
    con = duckdb.connect()
    rows = con.execute(f"DESCRIBE SELECT * FROM {read_sql(path)} LIMIT 0").fetchall()
    cols = [r[0] for r in rows]
    # strip BOM that DuckDB may leave on the first header cell
    cols[0] = cols[0].lstrip("﻿")
    return cols
