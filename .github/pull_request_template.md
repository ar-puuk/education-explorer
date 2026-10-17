## What and why

## Checks
- [ ] `ruff`, `pytest`, `svelte-check`, `vitest` pass
- [ ] `update` leaves `git status` clean on unchanged inputs (if the pipeline changed) and `validate` passes
- [ ] `web/e2e/smoke.mjs` passes in light and dark mode (if the app changed)
- [ ] No state literals, rankings or quality language added; caveats updated if needed
