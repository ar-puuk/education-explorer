# Decisions

Format: date, decision, why.

- 2026-10-16: Python 3.13 (pinned in `pipeline/.python-version`), `requires-python >=3.13`. Why: default per instructions; 3.14 is installed but 3.13 has the widest wheel coverage for duckdb/pyarrow.
- 2026-10-16: License MIT, repo `ar-puuk/education-explorer`, public from the start.
- 2026-10-16: Git author email is the maintainer's work address (global config); no noreply address is configured, so commits use it as-is. Global git config not changed.
- 2026-10-16: HANDOFF wording updated: repo is public from the start; Phase 0 (incl. Pages range spike) runs in this repo.
- 2026-10-16: Pages range requests verified; proceed. Pages enabled on main:/docs.
- 2026-10-16: CCD coordinates come from EDGE geocode files (CCD directory has none). Why: verified against the real file.
- 2026-10-16: CCD file discovery uses the NCES datatables JSON API; IPEDS discovery by HEAD-probing names on /ipeds/complete-data-files/. Why: no guessable listing; verified live.
- 2026-10-16: Utah is tiny (130 KB per membership year), so one Parquet per table-year, no splitting.
- 2026-10-16: Spike code kept in gitignored scratch/; only findings in SPIKES.md.
- 2026-10-16: CCD modern era (2014-15 onward, uniform CSV layouts) is built first (Phase 1); legacy 1986-87..2013-14 universe files (tab-delimited with year-suffixed names for 2006-2013, fixed-width/SAS for 1986-2005) are deferred to "Phase 1b" after the app exists. Why: the modern era is one consistent family and unblocks the product; legacy needs separate per-year maps and layouts.
- 2026-10-16: State (SEA) CCD files are not ingested; reconciliation uses district (LEA) files. Why: not needed for any planned table; 2014-15 SEA files are .xls.
- 2026-10-16: Schema maps are per topic per year YAML (pipeline/nces_pipeline/schemas/<source>/<topic>/<year>.yml). Wide 2014-15 files (and 2016+ long files) normalize to one long table via `unpivot` entries in the map. Why: the same table schema for the app across eras.
- 2026-10-16: value_flag vocabulary: reported, derived, adjusted, missing, not_applicable, not_reported, suppressed, not_meeting_standards, unknown_other. Sentinels: -1/M missing, -2/N/dagger not_applicable, -3 suppressed, -9/double-dagger not_meeting_standards. Missing/suppressed values are NULL, never 0.
- 2026-10-16: data_version is derived from NCES version label: 0a preliminary, 1a provisional, 2a final (2a=Final confirmed in NCES file names; 0a=preliminary confirmed for 2025-26 directory; 1a=provisional is NCES convention, not independently confirmed).
- 2026-10-16: Raw files are first staged to state-only VARCHAR Parquet (data-raw/_stage/) so the 2.3 GB national membership files are scanned once. Non-UTF-8 raw files are transcoded from cp1252 (DuckDB's latin-1 reader rejects cp1252 bytes). Deflate64 zips use the zipfile-deflate64 package.
- 2026-10-16: School coordinates: NCES EDGE (2014-15 from the CCD EDGE_GEOIDS csv; 2015-16..2024-25 from EDGE_GEOCODE_PUBLICSCH via the shapefile .dbf / file gdb, because the .TXT files are headerless with changing column order). Years with a CCD directory but no EDGE file (2025-26) carry forward each school's latest EDGE coordinates (coord_source=edge_prior_year); schools with none are left for the geocoder.
- 2026-10-16: lat/lon columns use `signed: true` in maps so negative longitudes are not treated as sentinels (a bug caught by validate/dictionary).
- 2026-10-16: validate gate: uniqueness, <90 MB, bbox, school-vs-district membership reconciliation (report; warn >2%), YoY swings (report), dictionary completeness, no state literal in outputs/paths, row-count drop vs baseline (fails at >20%). `update` is idempotent: a second run leaves git clean.
- 2026-10-16: `--state` defaults to the only config present, so no state literal is in code. Python writes use LF newlines so outputs are identical across OSes.
