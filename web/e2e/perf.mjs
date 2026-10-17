// Rough performance numbers: node e2e/perf.mjs <baseUrl>
import { chromium } from 'playwright'
const base = process.argv[2] ?? 'http://localhost:4173/'
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const ctx = await browser.newContext({ viewport: { width: 1360, height: 820 } })
const page = await ctx.newPage()
let bytes = 0
const sizes = {}
page.on('response', async (r) => {
  try {
    const len = (await r.body()).length
    bytes += len
    const k = new URL(r.url()).pathname.split('/').slice(-1)[0].replace(/-[A-Za-z0-9_]{6,}\./, '.')
    sizes[k] = (sizes[k] ?? 0) + len
  } catch {}
})
const t0 = Date.now()
await page.goto(base, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => {
  const m = window.__ee?.controller?.map
  return m && m.getLayer('public-points') && m.queryRenderedFeatures({ layers: ['public-points', 'public-clusters'] }).length > 0
}, null, { timeout: 60000 })
const tMarkers = Date.now() - t0
await page.locator('#school-search').fill('high')
const t1 = Date.now()
await page.locator('#search-results li button').first().click()
await page.waitForSelector('aside[aria-label="School details"] svg', { timeout: 90000 })
const tPanel = Date.now() - t1
const top = Object.entries(sizes).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k, v]) => `${k} ${(v / 1e6).toFixed(2)}MB`)
console.log(`first markers: ${tMarkers} ms; first detail panel (includes DuckDB-WASM startup): ${tPanel} ms; total transferred: ${(bytes / 1e6).toFixed(1)} MB`)
console.log('largest:', top.join(', '))
await browser.close()
