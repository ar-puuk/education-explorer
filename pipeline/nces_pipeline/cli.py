"""Command line: python -m nces_pipeline <command> --state utah ..."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

from .config import load_state


def _ccd_cols(cf_staged: Path) -> list[str]:
    con = duckdb.connect()
    return [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{cf_staged.as_posix()}')").fetchall()]


def cmd_fetch(a, state) -> int:
    from .catalog import build_catalog
    from .ccd_files import fetch_all, select

    if a.source in (None, "ccd"):
        build_catalog(refresh=a.check_only or a.refresh_catalog)
        files = select(min_year=a.year or 0, max_year=a.year or 9999)
        if a.check_only:
            from .config import DATA_RAW

            new = [f for f in files if not (DATA_RAW / f.rel).exists()]
            print(f"CCD: {len(files)} files in catalog, {len(new)} not downloaded yet")
            for f in new:
                print(f"  NEW {f.school_year} {f.level} {f.component}: {f.url} ({f.size})")
        else:
            got = fetch_all(files)
            print(f"CCD: {len(got)} of {len(files)} files present")
    if a.source in (None, "edge"):
        from .edge import fetch_edge

        fetch_edge(check_only=a.check_only)
    return 0


def cmd_bootstrap(a, state) -> int:
    """Create first-time maps for every CCD topic/year that lacks one (review TODOs afterwards)."""
    from .ccd_build import raw_files, raw_path_for, write_bootstrap_map
    from .ccd_topics import TOPICS
    from .stage import stage

    files = raw_files()
    for topic in TOPICS.values():
        for (y, comp), cf in sorted(files.items()):
            if comp != topic.component or (a.year and y != a.year):
                continue
            staged = stage(raw_path_for(cf), state)
            p = write_bootstrap_map(topic, y, _ccd_cols(staged), force=a.force)
            print("map:", p.name, topic.name)
    from .edge import FIRST, LAST, edge_table_source, write_edge_map

    for y in range(FIRST, LAST + 1):
        if edge_table_source(y) and (not a.year or a.year == y):
            write_edge_map(y, force=a.force)
    return 0


def cmd_build(a, state) -> int:
    if a.scaffold_map:
        from .ccd_build import raw_files, raw_path_for
        from .ccd_topics import TOPICS
        from .schema import scaffold
        from .stage import stage

        source, topic, year = a.scaffold_map[0], a.scaffold_map[1], int(a.scaffold_map[2])
        cf = raw_files()[(year, TOPICS[topic].component)]
        cols = _ccd_cols(stage(raw_path_for(cf), state))
        print("scaffolded", scaffold(source, topic, year, cols))
        return 0
    from .ccd_build import build_ccd
    from .edge import build_edge

    yrs = [a.year] if a.year else None
    if a.source in (None, "ccd"):
        build_ccd(state, years=yrs)
    if a.source in (None, "edge"):
        build_edge(state, years=yrs)
    if a.source in (None, "edge"):
        from .edge import build_carry_forward

        build_carry_forward(state)
    return 0


def cmd_validate(a, state) -> int:
    from .validate import validate

    rep = validate(state, update_baseline=a.update_baseline)
    rep.print()
    return 1 if rep.errors else 0


def cmd_update(a, state) -> int:

    from .dictionary import build_dictionary
    from .meta import write_meta
    from .validate import current_rowcounts

    before = current_rowcounts()
    ns = argparse.Namespace(source=None, year=a.year, check_only=False, refresh_catalog=False, scaffold_map=None)
    cmd_fetch(ns, state)
    cmd_build(ns, state)
    build_dictionary()
    write_meta(state)
    after = current_rowcounts()
    print("changelog:")
    changed = False
    for t in sorted(set(before) | set(after)):
        for y in sorted(set(before.get(t, {})) | set(after.get(t, {}))):
            b, c = before.get(t, {}).get(y), after.get(t, {}).get(y)
            if b != c:
                changed = True
                print(f"  {t}/{y}: {b} -> {c}")
    if not changed:
        print("  (no row-count changes)")
    return cmd_validate(argparse.Namespace(update_baseline=True), state)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nces_pipeline")
    ap.add_argument("--state", default="utah", help="config/states/<name>.yml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch")
    f.add_argument("--source", choices=["ccd", "edge", "pss", "ipeds"])
    f.add_argument("--year", type=int)
    f.add_argument("--check-only", action="store_true")
    f.add_argument("--refresh-catalog", action="store_true")
    f.set_defaults(fn=cmd_fetch)

    b = sub.add_parser("bootstrap-maps")
    b.add_argument("--year", type=int)
    b.add_argument("--force", action="store_true")
    b.set_defaults(fn=cmd_bootstrap)

    v = sub.add_parser("validate")
    v.add_argument("--update-baseline", action="store_true", help="record row counts as the new baseline when valid")
    v.set_defaults(fn=cmd_validate)

    u = sub.add_parser("update", help="fetch -> build -> dictionary -> meta -> validate, with a changelog")
    u.add_argument("--year", type=int)
    u.set_defaults(fn=cmd_update)

    dc = sub.add_parser("dictionary")
    dc.set_defaults(fn=lambda a, st: print("dictionary rows:", __import__("nces_pipeline.dictionary", fromlist=["x"]).build_dictionary()) or 0)

    bd = sub.add_parser("build")
    bd.add_argument("--source", choices=["ccd", "edge", "pss", "ipeds"])
    bd.add_argument("--year", type=int)
    bd.add_argument("--scaffold-map", nargs=3, metavar=("SOURCE", "TOPIC", "YEAR"))
    bd.set_defaults(fn=cmd_build)

    a = ap.parse_args(argv)
    return a.fn(a, load_state(a.state))


if __name__ == "__main__":
    sys.exit(main())
