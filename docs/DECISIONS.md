# Decisions

Format: date, decision, why.

- 2026-10-16: Python 3.13 (pinned in `pipeline/.python-version`), `requires-python >=3.13`. Why: default per instructions; 3.14 is installed but 3.13 has the widest wheel coverage for duckdb/pyarrow.
- 2026-10-16: License MIT, repo `ar-puuk/education-explorer`, public from the start.
- 2026-10-16: Git author email is the maintainer's work address (global config); no noreply address is configured, so commits use it as-is. Global git config not changed.
- 2026-10-16: HANDOFF wording updated: repo is public from the start; Phase 0 (incl. Pages range spike) runs in this repo.
