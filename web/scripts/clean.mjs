// Remove previously built app output from ../docs (never docs/data or docs/*.md).
import { rmSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const docs = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../docs')
for (const p of ['assets', 'index.html', 'favicon.svg']) {
  const f = path.join(docs, p)
  if (existsSync(f)) rmSync(f, { recursive: true, force: true })
}
