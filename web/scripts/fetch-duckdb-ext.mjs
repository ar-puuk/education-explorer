// Self-host the DuckDB-WASM Parquet extension (the engine would otherwise download it from extensions.duckdb.org
// at runtime). Version = the DuckDB core version bundled in @duckdb/duckdb-wasm (see scripts/duckdb-ext.json).
import { mkdirSync, existsSync, writeFileSync, readFileSync } from 'node:fs'
import path from 'node:path'
const root = path.resolve(import.meta.dirname, '..')
const { version, names } = JSON.parse(readFileSync(path.join(root, 'scripts/duckdb-ext.json'), 'utf8'))
for (const name of names) {
  const dest = path.join(root, 'public/duckdb-ext', version, 'wasm_eh', `${name}.duckdb_extension.wasm`)
  if (existsSync(dest)) continue
  const url = `https://extensions.duckdb.org/${version}/wasm_eh/${name}.duckdb_extension.wasm`
  const r = await fetch(url)
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`)
  mkdirSync(path.dirname(dest), { recursive: true })
  writeFileSync(dest, Buffer.from(await r.arrayBuffer()))
  console.log('fetched', url)
}
