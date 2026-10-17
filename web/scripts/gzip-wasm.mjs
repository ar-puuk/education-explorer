// GitHub Pages does not compress .wasm, so ship the DuckDB engine gzipped (36 MB -> ~8 MB)
// and let the browser inflate it (DecompressionStream). Runs after `vite build`.
import { readFileSync, writeFileSync, readdirSync, rmSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import path from 'node:path'
const dir = path.resolve(import.meta.dirname, '../../docs/assets')
for (const f of readdirSync(dir)) {
  if (!f.endsWith('.wasm')) continue
  const p = path.join(dir, f)
  writeFileSync(p + '.gz', gzipSync(readFileSync(p), { level: 9 }))
  rmSync(p)
  console.log('gzipped', f)
}
