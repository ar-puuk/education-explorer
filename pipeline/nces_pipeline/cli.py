"""Command line: python -m nces_pipeline <command> --state <name> ..."""
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
    from .ccd_build import CCD_FIRST_YEAR
    from .ccd_files import fetch_all, select

    if a.source in (None, "ccd"):
        build_catalog(refresh=a.check_only or a.refresh_catalog)
        files = select(min_year=a.year or CCD_FIRST_YEAR, max_year=a.year or 9999)
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
    if a.source in (None, "boundaries"):
        from .boundaries import fetch_boundaries

        print(f"TIGER school district files present: {fetch_boundaries(state)}")
    if a.source in (None, "pss"):
        from .pss import fetch_pss

        print(f"PSS: {fetch_pss()} surveys present")
    if a.source in (None, "ipeds"):
        from .config import DATA_RAW
        from .ipeds_catalog import build_catalog as ipeds_catalog
        from .ipeds_files import fetch_all as ipeds_fetch
        from .ipeds_files import select as ipeds_select

        ipeds_catalog(refresh=a.check_only or a.refresh_catalog)
        files = ipeds_select(min_year=a.year or 0, max_year=a.year or 9999)
        if a.check_only:
            new = [f for f in files if not (DATA_RAW / f.rel).exists()]
            print(f"IPEDS: {len(files)} files in scope, {len(new)} not downloaded yet")
            for f in new:
                print(f"  NEW {f.year} {f.name}: {f.title[:90]}")
        else:
            got = ipeds_fetch(files)
            print(f"IPEDS: {len(got)} of {len(files)} files present")
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
            p = write_bootstrap_map(topic, y, _ccd_cols(staged), force=a.force, staged=staged)
            print("map:", p.name, topic.name)
    from .edge import FIRST, LAST, edge_table_source, write_edge_map

    for y in range(FIRST, LAST + 1):
        if edge_table_source(y) and (not a.year or a.year == y):
            write_edge_map(y, force=a.force)
    from .ipeds_build import bootstrap_all

    bootstrap_all(state, force=a.force)
    from .pss import bootstrap as pss_bootstrap

    print("map:", pss_bootstrap(state, force=a.force).name)
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
    if a.source in (None, "ipeds"):
        from .ipeds_build import build_ipeds

        build_ipeds(state, years=yrs)
    if a.source in (None, "pss"):
        from .pss import build_pss

        build_pss(state)
    return 0


def cmd_validate(a, state) -> int:
    from .validate import validate

    rep = validate(state, update_baseline=a.update_baseline)
    rep.print()
    return 1 if rep.errors else 0


def cmd_geocode(a, state) -> int:
    from .geocode import apply_to_ccd_locations, geocode_pending

    st = geocode_pending(state, limit=a.limit)
    print(f"geocode: {st}")
    print(f"school locations filled from the geocode cache: {apply_to_ccd_locations()}")
    return 0


def cmd_boundaries(a, state) -> int:
    from .boundaries import build_boundaries, fetch_boundaries

    fetch_boundaries(state)
    build_boundaries(state)
    return 0


def cmd_points(a, state) -> int:
    from .geo import build_points_college, build_points_private, build_points_public

    print("public points:", build_points_public())
    print("college points:", build_points_college())
    print("private points:", build_points_private())
    return 0


def cmd_update(a, state) -> int:

    from .dictionary import build_dictionary
    from .meta import write_meta
    from .validate import current_rowcounts

    before = current_rowcounts()
    ns = argparse.Namespace(source=None, year=a.year, check_only=False, refresh_catalog=False, scaffold_map=None)
    cmd_fetch(ns, state)
    cmd_build(ns, state)
    cmd_geocode(argparse.Namespace(limit=None), state)
    cmd_boundaries(argparse.Namespace(), state)
    build_dictionary()
    from .geo import build_points_college, build_points_private, build_points_public

    build_points_public()
    build_points_college()
    build_points_private()
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


def _default_state() -> str | None:
    from .config import CONFIG_DIR

    found = sorted(p.stem for p in (CONFIG_DIR / "states").glob("*.yml"))
    return found[0] if len(found) == 1 else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nces_pipeline")
    ap.add_argument("--state", default=_default_state(), help="config/states/<name>.yml (default: the only one present)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch")
    f.add_argument("--source", choices=["ccd", "edge", "pss", "ipeds", "boundaries"])
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

    gc = sub.add_parser("geocode", help="geocode addresses that lack source coordinates (Census batch geocoder, cached)")
    gc.add_argument("--limit", type=int)
    gc.set_defaults(fn=cmd_geocode)

    bd2 = sub.add_parser("boundaries", help="build simplified school district boundary GeoJSON files")
    bd2.set_defaults(fn=cmd_boundaries)

    pt = sub.add_parser("points", help="build first-paint points files in docs/data/geo")
    pt.set_defaults(fn=cmd_points)

    dc = sub.add_parser("dictionary")
    dc.set_defaults(fn=lambda a, st: print("dictionary rows:", __import__("nces_pipeline.dictionary", fromlist=["x"]).build_dictionary()) or 0)

    bd = sub.add_parser("build")
    bd.add_argument("--source", choices=["ccd", "edge", "pss", "ipeds"])
    bd.add_argument("--year", type=int)
    bd.add_argument("--scaffold-map", nargs=3, metavar=("SOURCE", "TOPIC", "YEAR"))
    bd.set_defaults(fn=cmd_build)

    a = ap.parse_args(argv)
    if not a.state:
        ap.error("--state is required when several state configs exist")
    return a.fn(a, load_state(a.state))


if __name__ == "__main__":
    sys.exit(main())
