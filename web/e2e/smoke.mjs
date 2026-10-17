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
const BM = { positron: 'Positron', dark: 'Dark', liberty: 'Liberty', bright: 'Bright', fiord: 'Fiord' }
const setYear = async (y) => {
  const sl = page.getByRole('slider', { name: 'School year' })
  await sl.focus()
  await page.keyboard.press('Home')
  const min = Number(await sl.getAttribute('aria-valuemin'))
  for (let i = 0; i < y - min; i++) await page.keyboard.press('ArrowRight')
}
const insp = (label) => page.locator(`aside[aria-label="${label}"]`)

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
await page.getByRole('button', { name: 'Dark theme' }).click()
await idle()
const dark = await page.evaluate(() => [getComputedStyle(document.body).backgroundColor, window.__ee.controller.basemap])
dark[1] === 'dark' ? ok('dark theme switches default basemap to Dark') : fail('basemap after dark: ' + dark[1])
await page.waitForTimeout(1500)
await idle()
r = await rendered()
r.n > 0 ? ok(`dark: ${r.n} rendered features`) : fail('no features in dark mode')
await page.screenshot({ path: `${out}/02-dark.png` })

// every basemap keeps overlays
for (const id of ['liberty', 'bright', 'fiord', 'positron', 'dark']) {
  if (!(await page.getByRole('radiogroup', { name: 'Basemap style' }).isVisible())) await page.getByRole('button', { name: 'Basemap & appearance' }).click()
  await page.getByRole('radiogroup', { name: 'Basemap style' }).getByRole('radio', { name: BM[id], exact: true }).click()
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
await page.getByRole('button', { name: 'Light theme' }).click()
await page.waitForTimeout(500)
const kept = await page.evaluate(() => window.__ee.controller.basemap)
kept === 'dark' ? ok('explicit basemap choice survives theme change') : fail('explicit choice overridden: ' + kept)

// select a school via search; panel + chart
await page.getByRole('button', { name: 'System theme' }).click()
await page.locator('#school-search').fill(SCHOOL)
await page.locator('#search-results li button').first().click()
await page.waitForSelector('aside[aria-label="School details"] h2', { timeout: 20000 })
await page.waitForSelector('aside[aria-label="School details"] .card svg', { timeout: 60000 })
ok('detail panel with chart rendered')
await page.waitForTimeout(800)
await page.screenshot({ path: `${out}/03-detail.png` })
for (const t of ['Race/ethnicity', 'Sex', 'Grade']) {
  await insp('School details').getByRole('button', { name: t, exact: true }).click()
  await page.waitForTimeout(400)
}
await page.screenshot({ path: `${out}/04-detail-grade.png` })
for (const t of ['Trends', 'Details']) {
  await page.getByRole('tab', { name: t }).click()
  await page.waitForTimeout(500)
}
await page.getByRole('tab', { name: 'Trends' }).click()
await page.waitForSelector('aside[aria-label="School details"] .card svg', { timeout: 20000 })
ok('public school trends tab renders charts')
await page.getByRole('button', { name: 'Expand panel' }).click()
await page.waitForTimeout(400)
const wideW = await insp('School details').evaluate((e) => e.getBoundingClientRect().width)
wideW > 700 ? ok('inspector expands to workspace width: ' + Math.round(wideW)) : fail('inspector did not widen: ' + wideW)
await page.getByRole('button', { name: 'Shrink panel' }).click()

// college: search, panel, charts, table explorer
await page.locator('#school-search').fill(COLLEGE)
await page.locator('#search-results li button', { hasText: 'College' }).first().click()
await page.waitForSelector('aside[aria-label="College details"] h2', { timeout: 20000 })
await page.waitForSelector('aside[aria-label="College details"] svg', { timeout: 60000 })
ok('college panel with chart rendered')
for (const t of ['Level', 'Full/part-time', 'Gender', 'Race/ethnicity']) {
  await insp('College details').getByRole('button', { name: t, exact: true }).click()
  await page.waitForTimeout(300)
}
await page.waitForTimeout(500)
await page.screenshot({ path: `${out}/05-college.png` })
await page.getByRole('tab', { name: 'Data' }).click()
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
  await insp('Private school details').getByRole('button', { name: t, exact: true }).click()
  await page.waitForTimeout(300)
}
await setYear(2024)
await page.waitForTimeout(500)
const note = await page.locator('footer[aria-label=Timeline]').innerText();
/survey/.test(note) ? ok('timeline names the private survey year: ' + note.replace(/\n/g, ' / ')) : fail('no survey note at 2024: ' + note)
await setYear(2025)
const note25 = await insp('Private school details').locator('.yearline').innerText();
/biennial|survey/.test(note25) ? ok('private panel explains biennial surveys') : fail('private yearline: ' + note25)
await page.screenshot({ path: `${out}/07-private.png` })

// district: boundaries, search, panel with trends and rollup
await page.locator('#school-search').fill('district')
await page.locator('#search-results li button', { hasText: 'School district' }).first().click()
await page.waitForSelector('aside[aria-label="District details"] h2', { timeout: 20000 })
await page.waitForSelector('aside[aria-label="District details"] svg', { timeout: 60000 })
ok('district panel with chart rendered')
await page.getByRole('tab', { name: 'Trends' }).click()
for (const t of ['Staff', 'Finance', 'Students']) {
  await insp('District details').getByRole('button', { name: t, exact: true }).click()
  await page.waitForTimeout(400)
}
await page.getByRole('tab', { name: 'Schools' }).click()
await page.waitForSelector('aside[aria-label="District details"] .schools li', { timeout: 20000 })
ok('district school rollup listed')
const boundaryOn = await page.evaluate(() => window.__ee.controller.map.getLayoutProperty('districts-fill', 'visibility'))
boundaryOn === 'visible' ? ok('district boundaries shown after selecting a district') : fail('boundaries not visible: ' + boundaryOn)
await page.waitForTimeout(800)
await page.screenshot({ path: `${out}/08-district.png` })

// compare + table view
await page.getByRole('button', { name: /^\+ Compare$/ }).click()
await page.getByRole('button', { name: /^Open compare/ }).click()
await page.waitForSelector('[role=dialog][aria-label="Compare places"] svg', { timeout: 30000 })
ok('compare view renders a chart')
await page.screenshot({ path: `${out}/09-compare.png` })
await page.getByRole('button', { name: 'Close compare' }).click()
await page.getByRole('button', { name: 'Open data tables' }).click()
await page.waitForSelector('[role=dialog][aria-label="Table of places on the map"] tbody tr', { timeout: 20000 })
const nrows = await page.locator('[role=dialog][aria-label="Table of places on the map"] tbody tr').count()
nrows > 50 ? ok('table view lists rows: ' + nrows) : fail('table rows ' + nrows)
await page.screenshot({ path: `${out}/10-table.png` })
const dl2 = page.waitForEvent('download')
await page.locator('[role=dialog][aria-label="Table of places on the map"] button', { hasText: 'Download CSV' }).click()
ok('table CSV download: ' + (await dl2).suggestedFilename())
await page.getByRole('button', { name: 'Close table' }).click()

// methodology page
const mp = await ctx.newPage()
await mp.goto(base_ + 'methodology.html')
await mp.waitForSelector('#versions table', { timeout: 20000 })
ok('methodology page loads coverage table')
await mp.close()

// colour by attribute keeps markers on the map and changes the icon set
await page.getByRole('button', { name: 'Layers', exact: true }).click().catch(() => {})
if (!(await page.getByRole('group', { name: 'Colour public schools by' }).isVisible())) await page.getByRole('button', { name: 'Layers', exact: true }).click()
await page.getByRole('group', { name: 'Colour public schools by' }).getByRole('button', { name: 'Charter', exact: true }).click()
await page.waitForTimeout(600)
const catIcon = await page.evaluate(() => window.__ee.controller.map.hasImage('public-cat1'))
catIcon ? ok('colour-by icons registered') : fail('no category icons')
await page.getByRole('group', { name: 'Colour public schools by' }).getByRole('button', { name: 'One colour', exact: true }).click()

// legacy years (pre-2014) work: map markers and a school panel with its history
await page.locator('#school-search').fill(SCHOOL)
await page.locator('#search-results li button', { hasText: 'Public school' }).first().click()
await page.waitForSelector('aside[aria-label="School details"] .card svg', { timeout: 60000 })
await setYear(2003)
await page.waitForTimeout(1200)
await idle()
const legacyN = (await rendered()).n
legacyN > 0 ? ok(`2003-04: ${legacyN} rendered features`) : fail('no features in 2003')
const yl = await page.locator('aside[aria-label="School details"] .yearline').innerText()
const yearOk = /2003-04/.test(yl)
yearOk ? ok('school panel follows the year slider into legacy years') : fail('year line: ' + yl)

// URL state round trip
const url = page.url()
url.includes('sel=public%3A') || url.includes('sel=public:') ? ok('URL carries selection: ' + url.slice(-70)) : fail('URL missing selection: ' + url)
const p2 = await ctx.newPage()
p2.on('pageerror', (e) => errors.push('pageerror2: ' + e.message))
await p2.goto(url, { waitUntil: 'domcontentloaded' })
await p2.waitForSelector('aside[aria-label="School details"] h2', { timeout: 30000 })
ok('URL restores the selected school')

// year slider
await setYear(2018)
await page.waitForTimeout(800)
const label = await page.locator('footer[aria-label=Timeline] strong').innerText()
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
