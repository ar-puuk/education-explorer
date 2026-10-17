import * as duckdb from '@duckdb/duckdb-wasm'
import wasmUrl from '@duckdb/duckdb-wasm/dist/duckdb-eh.wasm?url'
import workerUrl from '@duckdb/duckdb-wasm/dist/duckdb-browser-eh.worker.js?url'

/** Absolute URL of a file under docs/data (works under any base path). */
export const dataUrl = (rel: string) => new URL(`data/${rel}`, document.baseURI).href

let dbPromise: Promise<duckdb.AsyncDuckDB> | null = null
let connPromise: Promise<duckdb.AsyncDuckDBConnection> | null = null
const registered = new Set<string>()

/** Production builds ship the engine gzipped (Pages does not compress .wasm); dev serves it raw. */
async function wasmSource(): Promise<string> {
  const url = new URL(wasmUrl, document.baseURI).href
  if (import.meta.env.DEV) return url
  const res = await fetch(url + '.gz')
  if (!res.ok) throw new Error(`DuckDB engine: HTTP ${res.status}`)
  let bytes = new Uint8Array(await res.arrayBuffer())
  // Some servers add Content-Encoding: gzip, in which case the browser already inflated it.
  if (bytes[0] === 0x1f && bytes[1] === 0x8b) {
    const inflated = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))
    bytes = new Uint8Array(await new Response(inflated).arrayBuffer())
  }
  const blob = new Blob([bytes], { type: 'application/wasm' })
  return URL.createObjectURL(blob)
}

function getDb(): Promise<duckdb.AsyncDuckDB> {
  dbPromise ??= (async () => {
    // The worker is loaded from a same-origin Vite asset URL (no CDN at runtime).
    const worker = new Worker(workerUrl)
    const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker)
    await db.instantiate(await wasmSource())
    return db
  })()
  return dbPromise
}

async function conn(): Promise<duckdb.AsyncDuckDBConnection> {
  connPromise ??= getDb().then(async (d) => {
    const c = await d.connect()
    // The Parquet extension is self-hosted (public/duckdb-ext, copied to docs/ by the build) so the app never
    // contacts extensions.duckdb.org at runtime.
    const repo = new URL('duckdb-ext', document.baseURI).href
    await c.query(`SET custom_extension_repository='${repo}'`)
    await c.query('LOAD parquet')
    return c
  })
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
