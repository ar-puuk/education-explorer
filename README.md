# Education Explorer

A static, zero-cost, map-first dashboard for exploring publicly available NCES data
(public K-12 from CCD, private K-12 from PSS, colleges from IPEDS) for one state at a time.
The state is chosen by a single config file (`config/states/<name>.yml`).

Status: under active development. See [PROGRESS.md](PROGRESS.md), [HANDOFF.md](HANDOFF.md),
[docs/DECISIONS.md](docs/DECISIONS.md) and [SPIKES.md](SPIKES.md).

## Layout
- `config/` state, source and app configuration
- `pipeline/` Python (uv) preprocessing: fetch, build Parquet, geocode, validate
- `web/` Vite + Svelte + TypeScript app (builds into `docs/`)
- `docs/` GitHub Pages root; processed Parquet lives in `docs/data/`
- `data-raw/` local raw downloads (gitignored; only `manifest.json` is tracked)

## Quickstart
```
cd pipeline && uv sync
uv run python -m nces_pipeline --help
```

## Data attribution
See [DATA_ATTRIBUTION.md](DATA_ATTRIBUTION.md). Code is MIT licensed ([LICENSE](LICENSE)).
This project is not affiliated with or endorsed by NCES or the U.S. Census Bureau.
