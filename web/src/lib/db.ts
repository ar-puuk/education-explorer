import * as duckdb from '@duckdb/duckdb-wasm'
import wasmUrl from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url'
import workerUrl from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url'

/** Absolute URL of a file under docs/data (works under any base path). */
export const dataUrl = (rel: string) => new URL(`data/${rel}`, document.baseURI).href

let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null
let connPromise: Promise<duckdb.AsyncDuckDBConnection> | null = null
const registered = new Set<string>()

function getDb(): Promise<duckdb.AsyncDuckDB> {
  dbPromise ??= (async () => {
    // The worker is loaded from a same-origin Vite asset URL (no CDN at runtime).
    const worker = new Worker(workerUrl)
    const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker)
    await db.instantiate(new URL(wasmUrl, document.baseURI).href)
    return db
  })()
  return dbPromise
}

async function conn(): Promise<duckdb.AsyncDuckDBConnection> {
  connPromise ??= getDb().then((d) => d.connect())
  return connPromise
}

/** Register Parquet files by relative path (e.g. "ccd/membership/2024.parquet"); returns DuckDB file names. */
async function register(rels: string[]): Promise<string[]> {
  const db = await getDb()
  const names: string[] = []
  for (const rel of rels) {
    const name = rel.replaceAll('/', '__')
    if (!registered.has(name)) {
      await db.registerFileURL(name, dataUrl(rel), duckdb.DuckDBDataProtocol.HTTP, false)
      registered.add(name)
    }
    names.push(name)
  }
  return names
}

export type Row = Record<string, unknown>

function plain(v: unknown): unknown {
  if (typeof v === 'bigint') return Number(v)
  return v
}

/** Query Parquet files over HTTP. `{files}` in the SQL is replaced by a read_parquet(...) source.
 *  Parameters use `?` placeholders. */
export async function queryParquet(rels: string[], sql: string, params: (string | number)[] = []): Promise<Row[]> {
  if (!rels.length) return []
  const names = await register(rels)
  const c = await conn()
  const src = `read_parquet([${names.map((n) => `'${n}'`).join(',')}], union_by_name=true)`
  const text = sql.replaceAll('{files}', src)
  const stmt = await c.prepare(text)
  const res = await stmt.query(...params)
  await stmt.close()
  return res.toArray().map((r) => {
    const o: Row = {}
    for (const f of res.schema.fields) o[f.name] = plain(r[f.name])
    return o
  })
}

/** Start loading the engine in the background (called after first paint). */
export function warmUp(): Promise<unknown> {
  return conn()
}
