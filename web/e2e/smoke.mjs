// Browser smoke test: node e2e/smoke.mjs <baseUrl> [outDir]
// Checks: first paint with markers, light/dark, basemap switching keeps overlays, detail panel + charts.
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const base = process.argv[2] ?? 'http://localhost:5173/'
const out = process.argv[3] ?? 'e2e/shots'
mkdirSync(out, { recursive: true })

const errors = []
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const ctx = await browser.newContext({ viewport: { width: 1360, height: 820 }, colorScheme: 'light' })
const page = await ctx.newPage()
const hosts = new Set()
page.on('request', (r) => hosts.add(new URL(r.url()).host))
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
page.on('console', (m) => {
  if (m.type() === 'error' && !/favicon|Failed to load resource.*(tiles|fonts|sprites)/i.test(m.text())) errors.push('console: ' + m.text().slice(0, 200))
})

// pick test subjects from the data itself (no state literals)
const base_ = base.endsWith('/') ? base : base + '/'
const pub = await (await fetch(base_ + 'data/geo/points_public.json')).json()
const col = await (await fetch(base_ + 'data/geo/points_college.json')).json()
const biggest = (arr) => arr.reduce((a, b) => ((b.enroll.at(-2) ?? 0) > (a.enroll.at(-2) ?? 0) ? b : a))
const SCHOOL = biggest(pub.schools).name
const COLLEGE = biggest(col.institutions).name
const priv = await (await fetch(base_ + 'data/geo/points_private.json')).json()
const PRIVATE = priv.schools.reduce((a, b) => ((b.enroll.at(-1) ?? 0) > (a.enroll.at(-1) ?? 0) ? b : a)).name

const fail = (msg) => {
  console.error('FAIL:', msg)
  process.exitCode = 1
}
const ok = (msg) => console.log('ok:', msg)

const rendered = () =>
  page.evaluate(() => {
    const m = window.__ee.controller.map
    const layers = ['public-points', 'public-clusters'].filter((l) => m.getLayer(l))
    return { layers: layers.length, n: layers.length ? m.queryRenderedFeatures({ layers }).length : -1, style: m.isStyleLoaded() }
  })
const idle = () => page.evaluate(() => new Promise((res) => { const m = window.__ee.controller.map; if (m.loaded() && !m.isMoving()) res(true); else m.once('idle', () => res(true)) }))

await page.goto(base, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => window.__ee?.controller?.map, null, { timeout: 30000 })
await idle()
await page.waitForFunction(() => {
  const m = window.__ee.controller.map
  return m.getLayer('public-points') && m.queryRenderedFeatures({ layers: ['public-points', 'public-clusters'] }).length > 0
}, null, { timeout: 30000 })
let r = await rendered()
r.n > 0 ? ok(`first paint: ${r.n} rendered features`) : fail('no rendered features at first paint')
await page.screenshot({ path: `${out}/01-light.png` })

// dark theme via the control
await page.getByRole('button', { name: 'Dark', exact: true }).click()
await idle()
const dark = await page.evaluate(() => [getComputedStyle(document.body).backgroundColor, window.__ee.controller.basemap])
dark[1] === 'dark' ? ok('dark theme switches default basemap to Dark') : fail('basemap after dark: ' + dark[1])
await page.waitForTimeout(1500)
await idle()
r = await rendered()
r.n > 0 ? ok(`dark: ${r.n} rendered features`) : fail('no features in dark mode')
await page.screenshot({ path: `${out}/02-dark.png` })

// every basemap keeps overlays
for (const id of ['liberty', 'liberty3d', 'bright', 'fiord', 'positron', 'dark']) {
  await page.locator('header select').selectOption(id)
  await page.waitForTimeout(800)
  await idle()
  await page.waitForFunction(() => window.__ee.controller.map.getLayer('public-points'), null, { timeout: 15000 }).catch(() => {})
  await page.waitForTimeout(600)
  r = await rendered()
  const b = await page.evaluate(() => window.__ee.controller.basemap)
  b === id && r.n > 0 ? ok(`basemap ${id}: overlays intact (${r.n})`) : fail(`basemap ${id}: basemap=${b}, features=${r.n}`)
  await page.screenshot({ path: `${out}/basemap-${id}.png` })
}

// auto basemap follows theme when the user has not chosen; here the user chose, so it must not change
await page.getByRole('button', { name: 'Light', exact: true }).click()
await page.waitForTimeout(500)
const kept = await page.evaluate(() => window.__ee.controller.basemap)
kept === 'dark' ? ok('explicit basemap choice survives theme change') : fail('explicit choice overridden: ' + kept)

// select a school via search; panel + chart
await page.getByRole('button', { name: 'System', exact: true }).click()
await page.locator('#school-search').fill(SCHOOL)
await page.locator('#search-results li button').first().click()
await page.waitForSelector('aside[aria-label="School details"] h2', { timeout: 20000 })
await page.waitForSelector('aside[aria-label="School details"] svg', { timeout: 60000 })
ok('detail panel with chart rendered')
await page.waitForTimeout(800)
await page.screenshot({ path: `${out}/03-detail.png` })
for (const t of ['Race/ethnicity', 'Sex', 'Grade']) {
  await page.getByRole('tab', { name: t }).click()
  await page.waitForTimeout(400)
}
await page.screenshot({ path: `${out}/04-detail-grade.png` })

// college: search, panel, charts, table explorer
await page.locator('#school-search').fill(COLLEGE)
await page.locator('#search-results li button', { hasText: 'College' }).first().click()
await page.waitForSelector('aside[aria-label="College details"] h2', { timeout: 20000 })
await page.waitForSelector('aside[aria-label="College details"] svg', { timeout: 60000 })
ok('college panel with chart rendered')
for (const t of ['Level', 'Full/part-time', 'Gender', 'Race/ethnicity']) {
  await page.getByRole('tab', { name: t }).click()
  await page.waitForTimeout(300)
}
await page.waitForTimeout(500)
await page.screenshot({ path: `${out}/05-college.png` })
await page.locator('aside[aria-label="College details"] .explorer select').first().selectOption('efa')
await page.waitForSelector('aside[aria-label="College details"] .explorer table', { timeout: 30000 })
ok('table explorer shows a table')
await page.locator('aside[aria-label="College details"] .explorer').scrollIntoViewIfNeeded()
await page.screenshot({ path: `${out}/06-explorer.png` })
const dls = page.waitForEvent('download')
await page.getByRole('button', { name: 'Download CSV' }).click()
const dl = await dls
ok('CSV download: ' + dl.suggestedFilename())

// private school: search, panel, biennial note
await page.locator('#school-search').fill(PRIVATE)
await page.locator('#search-results li button', { hasText: 'Private school' }).first().click()
await page.waitForSelector('aside[aria-label="Private school details"] h2', { timeout: 20000 })
await page.waitForSelector('aside[aria-label="Private school details"] svg', { timeout: 60000 })
ok('private school panel with chart rendered')
for (const t of ['Grade', 'Race/ethnicity', 'Sex']) {
  await page.getByRole('tab', { name: t }).click()
  await page.waitForTimeout(300)
}
await page.locator('input[type=range]').fill('2024')
await page.waitForTimeout(500)
const note = await page.locator('.slider .note').allInnerTexts()
note.some((t) => /biennial/.test(t)) ? ok('slider explains biennial survey: ' + note.join(' / ')) : fail('no biennial note at 2024: ' + note.join('|'))
await page.screenshot({ path: `${out}/07-private.png` })

// district: boundaries, search, panel with trends and rollup
await page.locator('#school-search').fill('school district')
await page.locator('#search-results li button', { hasText: 'School district' }).first().click()
await page.waitForSelector('aside[aria-label="District details"] h2', { timeout: 20000 })
await page.waitForSelector('aside[aria-label="District details"] svg', { timeout: 60000 })
ok('district panel with chart rendered')
for (const t of ['Staff', 'Finance', 'Students', 'Enrollment']) {
  await page.getByRole('tab', { name: t }).click()
  await page.waitForTimeout(400)
}
await page.waitForSelector('aside[aria-label="District details"] .schools li', { timeout: 20000 })
ok('district school rollup listed')
const boundaryOn = await page.evaluate(() => window.__ee.controller.map.getLayoutProperty('districts-fill', 'visibility'))
boundaryOn === 'visible' ? ok('district boundaries shown after selecting a district') : fail('boundaries not visible: ' + boundaryOn)
await page.waitForTimeout(800)
await page.screenshot({ path: `${out}/08-district.png` })

// compare + table view
await page.getByRole('button', { name: /^\+ Compare$/ }).click()
await page.getByRole('button', { name: /^Compare/ }).first().click()
await page.waitForSelector('[role=dialog][aria-label="Compare places"] svg', { timeout: 30000 })
ok('compare view renders a chart')
await page.screenshot({ path: `${out}/09-compare.png` })
await page.getByRole('button', { name: 'Close compare' }).click()
await page.getByRole('button', { name: 'Table', exact: true }).click()
await page.waitForSelector('[role=dialog][aria-label="Table of places on the map"] tbody tr', { timeout: 20000 })
const nrows = await page.locator('[role=dialog][aria-label="Table of places on the map"] tbody tr').count()
nrows > 50 ? ok('table view lists rows: ' + nrows) : fail('table rows ' + nrows)
await page.screenshot({ path: `${out}/10-table.png` })
const dl2 = page.waitForEvent('download')
await page.getByRole('button', { name: 'Download CSV' }).click()
ok('table CSV download: ' + (await dl2).suggestedFilename())
await page.getByRole('button', { name: 'Close table' }).click()

// methodology page
const mp = await ctx.newPage()
await mp.goto(base_ + 'methodology.html')
await mp.waitForSelector('#versions table', { timeout: 20000 })
ok('methodology page loads coverage table')
await mp.close()

// URL state round trip
const url = page.url()
url.includes('sel=district%3A') || url.includes('sel=district:') ? ok('URL carries selection: ' + url.slice(-70)) : fail('URL missing selection: ' + url)
const p2 = await ctx.newPage()
p2.on('pageerror', (e) => errors.push('pageerror2: ' + e.message))
await p2.goto(url, { waitUntil: 'domcontentloaded' })
await p2.waitForSelector('aside[aria-label="District details"] h2', { timeout: 30000 })
ok('URL restores the selected district')

// year slider
await page.locator('input[type=range]').fill('2018')
await page.waitForTimeout(800)
const label = await page.locator('.slider strong').innerText()
label === '2018-19' ? ok('year slider -> 2018-19') : fail('slider label ' + label)

const allowed = new Set([new URL(base).host, 'tiles.openfreemap.org', ''])
const extra = [...hosts].filter((h) => !allowed.has(h))
extra.length ? fail('unexpected third-party hosts at runtime: ' + extra.join(', ')) : ok('only the app origin and tiles.openfreemap.org were contacted')
await browser.close()
if (errors.length) {
  console.error('ERRORS:\n' + errors.join('\n'))
  process.exitCode = 1
}
console.log(process.exitCode ? 'SMOKE FAILED' : 'SMOKE PASSED')
