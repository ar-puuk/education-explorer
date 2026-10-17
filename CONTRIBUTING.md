# Contributing

Thanks for helping. This is a small, zero-cost, static project; please keep it that way.

## Ground rules (locked decisions)

- No paid services, no backend, no GitHub Actions workflows, no runtime CDN dependencies, no data from the Urban Institute Education Data API: data come from the original NCES and Census files.
- The app shows data and caveats only. **Do not add rankings, quality scores, ratings or "best/worst" language.**
- No state literals in code, SQL or UI. A state is one file in `config/states/`.
- Processed Parquet is committed under `docs/data/` only after `validate` passes. Raw downloads are never committed (only `data-raw/manifest.json`). No Git LFS (Pages does not serve LFS files).
- Parquet must be deterministic: re-running `update` on unchanged inputs must leave `git status` clean.
- Light and dark themes and basemap switching must keep working (run `web/e2e/smoke.mjs`).

## Development

See the Quickstart in the [README](README.md). Before opening a pull request:

```bash
cd pipeline && uv run ruff check . && uv run pytest -q
cd ../web && npx svelte-check --tsconfig ./tsconfig.app.json && npx vitest run && npm run build
node e2e/smoke.mjs http://localhost:4173/ shots   # after `npm run preview`
```

Keep commits small and readable. Record decisions that are not obvious in `docs/DECISIONS.md` (date, decision, why).

## Typical contributions

- **A new NCES release breaks the build:** the drift guard lists the new or missing columns; edit the YAML map and add a test if the fix needs logic.
- **A new table or topic:** add a topic (CCD: `ccd_topics.py`) or let `bootstrap-maps` create the IPEDS/PSS map, write caveats in `config/caveats.yml`, make sure the dictionary has every column, and extend `validate.py` keys if needed.
- **Dictionary or caveat wording:** edit `config/caveats.yml` (facts tied to NCES documentation only).
- **Accessibility or layout fixes:** please include a screenshot in light and dark mode.

## Reporting data problems

Please include the dataset, table, year and ID, what you expected, and a link to the NCES source if you have one. Data issues in the NCES files themselves can only be reported to NCES.
