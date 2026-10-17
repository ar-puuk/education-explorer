// The data and methodology page: node e2e/methodology.mjs <baseUrl> <outDir>
// Live numbers, contents list, glossary and coverage filters, copy buttons, fonts, accessibility (axe, both themes) and phone width.
import { chromium } from 'playwright'
import AxeBuilder from '@axe-core/playwright'
import { mkdirSync } from 'node:fs'

const base = (process.argv[2] ?? 'http://localhost:4173/').replace(/\/?$/, '/')
const out = process.argv[3] ?? 'e2e/shots'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch()
let bad = 0
const ok = (m) => console.log('ok:', m)
const fail = (m) => {
  console.error('FAIL:', m)
  bad++
}

async function open(scheme, viewport) {
  const ctx = await browser.newContext({ viewport, colorScheme: scheme, permissions: ['clipboard-read', 'clipboard-write'] })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => {
    if (m.type() === 'error' && !/favicon/i.test(m.text())) errors.push('console: ' + m.text().slice(0, 160))
  })
  page.on('requestfailed', (r) => errors.push('request failed: ' + r.url()))
  await page.goto(base + 'methodology.html', { waitUntil: 'networkidle' })
  await page.waitForSelector('#versions li.cv', { timeout: 20000 })
  return { ctx, page, errors }
}

for (const scheme of ['light', 'dark']) {
  const { ctx, page, errors } = await open(scheme, { width: 1360, height: 900 })

  // live numbers and state name
  const stats = await page.locator('#stats .stat b').allTextContents()
  stats.length >= 5 && stats.every((t) => /\d/.test(t)) ? ok(`${scheme}: ${stats.length} live figures (${stats.slice(0, 3).join(', ')})`) : fail(`${scheme}: live figures missing: ${stats}`)
  const states = await page.locator('[data-state]').allTextContents()
  states.every((t) => t.trim() && t !== 'one state') ? ok(`${scheme}: state name filled from data (${states[0]})`) : fail(`${scheme}: state name not filled: ${states}`)
  const yrs = await page.locator('#yrs-ccd, #yrs-pss, #yrs-ipeds').allTextContents()
  yrs.every((t) => /\d{4}/.test(t)) ? ok(`${scheme}: dataset year ranges filled`) : fail(`${scheme}: year ranges: ${yrs}`)

  // fonts are the self-hosted ones
  const fonts = await page.evaluate(async () => {
    await document.fonts.ready
    return ['16px "Instrument Sans Variable"', '600 16px "Bricolage Grotesque Variable"', '400 14px "IBM Plex Mono"'].map((f) => document.fonts.check(f))
  })
  fonts.every(Boolean) ? ok(`${scheme}: self-hosted fonts loaded`) : fail(`${scheme}: fonts not loaded ${fonts}`)

  // contents list: every link points at a real section, and scrolling highlights one
  const hrefs = await page.locator('#toc a').evaluateAll((as) => as.map((a) => a.getAttribute('href')))
  const missing = []
  for (const h of hrefs) if (!(await page.locator(h).count())) missing.push(h)
  hrefs.length === 10 && !missing.length ? ok(`${scheme}: 10 contents links all resolve`) : fail(`${scheme}: contents links ${hrefs.length}, missing ${missing}`)
  await page.locator('#toc a[href="#charts"]').click()
  // smooth scrolling takes a moment; wait for it to settle on the right section
  const spied = await page.waitForFunction(() => document.querySelector('#toc a.on')?.getAttribute('href') === '#charts', null, { timeout: 8000 }).then(() => true, () => false)
  spied ? ok(`${scheme}: contents highlights the current section`) : fail(`${scheme}: scroll spy shows ${await page.locator('#toc a.on').first().getAttribute('href', { timeout: 1000 }).catch(() => 'nothing')}`)
  await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }))
  await page.waitForTimeout(600)
  ;(await page.locator('#toc a.on').count()) === 0 ? ok(`${scheme}: nothing highlighted at the top of the page`) : fail(`${scheme}: a section stays highlighted at the top`)

  // chart guide
  const rows = await page.locator('#charts li.cr').count()
  rows >= 15 ? ok(`${scheme}: chart guide lists ${rows} charts`) : fail(`${scheme}: chart guide rows ${rows}`)
  await page.locator('#expand').click()
  const openFolds = await page.locator('#charts details.fold[open]').count()
  openFolds === 4 ? ok(`${scheme}: open-all works`) : fail(`${scheme}: open folds ${openFolds}`)

  // glossary
  const total = await page.locator('#gl > div').count()
  await page.locator('#gl-q').fill('net price')
  const vis = await page.locator('#gl > div:not([hidden])').count()
  vis >= 1 && vis < total ? ok(`${scheme}: glossary filter ${vis} of ${total}`) : fail(`${scheme}: glossary filter ${vis}/${total}`)
  await page.locator('#gl-q').fill('zzzz')
  ;(await page.locator('#gl-none').isVisible()) ? ok(`${scheme}: glossary empty state`) : fail(`${scheme}: no empty state`)
  await page.locator('#gl-q').fill('')

  // coverage
  const before = await page.locator('#versions li.cv').count()
  await page.locator('#cov-seg button[data-ds="pss"]').click()
  const pssRows = await page.locator('#versions li.cv').count()
  pssRows === 3 ? ok(`${scheme}: coverage filter by dataset (${pssRows} PSS tables)`) : fail(`${scheme}: PSS rows ${pssRows}`)
  await page.locator('#cov-seg button[data-ds=""]').click()
  const more = page.locator('#cov-more')
  if (await more.count()) {
    await more.click()
    const all = await page.locator('#versions li.cv').count()
    all > before ? ok(`${scheme}: show-all expands the coverage table (${before} to ${all})`) : fail(`${scheme}: show all did not expand`)
  }
  await page.locator('#cov-q').fill('membership')
  const q = await page.locator('#versions li.cv').count()
  q >= 2 ? ok(`${scheme}: coverage text filter (${q} rows)`) : fail(`${scheme}: text filter rows ${q}`)
  const strips = await page.locator('#versions svg.cov rect').count()
  strips > 0 ? ok(`${scheme}: coverage strips drawn`) : fail(`${scheme}: no coverage strips`)
  await page.locator('#cov-q').fill('')

  // copy buttons
  await page.locator('button[data-copy="q-duck"]').click()
  const clip = await page.evaluate(() => navigator.clipboard.readText()).catch(() => '')
  clip.includes('read_parquet') && clip.includes('/data/ccd/membership/2024.parquet') && !clip.includes('…') ? ok(`${scheme}: copy button copies a working query`) : fail(`${scheme}: clipboard: ${clip.slice(0, 80)}`)
  // the example URL really exists
  const url = clip.match(/'([^']+\.parquet)'/)?.[1]
  if (url) {
    const r = await page.request.get(url, { headers: { Range: 'bytes=0-3' } })
    r.ok() ? ok(`${scheme}: example Parquet URL resolves`) : fail(`${scheme}: example URL ${url} -> ${r.status()}`)
  }

  // theme button cycles
  const t0 = await page.locator('#theme').textContent()
  await page.locator('#theme').click()
  const t1 = await page.locator('#theme').textContent()
  t0 !== t1 ? ok(`${scheme}: theme button cycles (${t0} -> ${t1})`) : fail(`${scheme}: theme button inert`)
  await page.locator('#theme').click()
  await page.locator('#theme').click()

  // axe with everything open
  await page.evaluate(() => document.querySelectorAll('details').forEach((d) => (d.open = true)))
  await page.locator('#cov-seg button[data-ds=""]').click()
  const ax = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  ax.violations.length ? fail(`${scheme}: axe ${ax.violations.map((v) => `${v.id} (${v.nodes.length}) ${v.nodes[0].target}`).join('; ')}`) : ok(`${scheme}: axe clean`)

  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({ path: `${out}/method-${scheme}-top.png` })
  await page.screenshot({ path: `${out}/method-${scheme}-full.png`, fullPage: true })
  errors.length ? errors.forEach((e) => fail(`${scheme}: ${e}`)) : ok(`${scheme}: no console errors or failed requests`)
  await ctx.close()
}

// phone
{
  const { ctx, page, errors } = await open('light', { width: 390, height: 800 })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)
  overflow ? fail('phone: page scrolls sideways') : ok('phone: no sideways scroll')
  const tocVisible = await page.locator('details.toc-m').isVisible()
  tocVisible ? ok('phone: collapsible contents shown') : fail('phone: no contents')
  await page.locator('details.toc-m summary').click()
  await page.locator('#toc-m a[href="#terms"]').click()
  await page.waitForTimeout(700)
  const top = await page.locator('#terms').evaluate((e) => Math.round(e.getBoundingClientRect().top))
  top >= 0 && top < 160 ? ok('phone: contents link scrolls to the section below the bar') : fail(`phone: section top at ${top}`)
  const small = await page.evaluate(() => [...document.querySelectorAll('button, a.back, a.path, summary, input, select')].filter((e) => e.offsetParent && (e.getBoundingClientRect().height < 24)).map((e) => (e.textContent || e.id || e.tagName).trim().slice(0, 24)))
  small.length ? fail('phone: small targets: ' + small.join(', ')) : ok('phone: controls at least 24px tall')
  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({ path: `${out}/method-phone-top.png` })
  await page.locator('#officials').scrollIntoViewIfNeeded()
  await page.screenshot({ path: `${out}/method-phone-officials.png` })
  errors.length ? errors.forEach((e) => fail(`phone: ${e}`)) : ok('phone: no console errors')
  await ctx.close()
}
await browser.close()
console.log(bad ? 'METHODOLOGY FAILED' : 'METHODOLOGY PASSED')
process.exitCode = bad ? 1 : 0
