// Touch layout: every chart on a phone viewport with touch emulation. node e2e/touch.mjs <baseUrl> <outDir>
// For each chart tab of each kind of place: no horizontal overflow, nothing clipped by its card, every chart reacts to a tap
// with a tooltip, tap targets are big enough, and the page never scrolls sideways.
import { chromium, devices } from 'playwright'
import { mkdirSync } from 'node:fs'

const base = process.argv[2] ?? 'http://localhost:4173/'
const out = process.argv[3] ?? 'e2e/shots'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
let bad = 0
let checked = 0
const fail = (m) => {
  console.error('FAIL:', m)
  bad++
}
const ok = (m) => console.log('ok:', m)

const CASES = [
  { kind: 'College', term: 'university', label: /College/, aside: 'College details', tabs: ['Overview', 'Students', 'Outcomes', 'Costs', 'Details'] },
  { kind: 'Public school', term: 'elementary', label: /Public school/, aside: 'School details', tabs: ['Overview', 'Students', 'Programs', 'Trends', 'Details'] },
  { kind: 'Private school', term: 'academy', label: /Private school/, aside: 'Private school details', tabs: ['Overview', 'Students', 'Trends', 'Details'] },
  { kind: 'District', term: 'district', label: /district/i, aside: 'District details', tabs: ['Overview', 'Students', 'Money', 'Trends', 'Details'] },
]

const POINT = `(root, i) => {
  const c = root.querySelectorAll('.chart')[i]
  const svg = [...c.querySelectorAll('svg')].find((s) => s.getAttribute('role') === 'img')
  if (!svg) return null
  const pick = (els) => els.map((e) => ({ e, r: e.getBoundingClientRect() })).filter(({ r }) => r.width > 2 && r.height > 2)
  const sr = svg.getBoundingClientRect()
  const dots = pick([...svg.querySelectorAll('circle')])
  const bars = pick([...svg.querySelectorAll('rect')]).filter(({ r }) => r.width < sr.width * 0.9 && r.height < sr.height * 0.95)
  const t = dots[Math.floor(dots.length / 2)] ?? bars[Math.floor(bars.length / 2)]
  if (!t) return { alt: svg.getAttribute('aria-label'), none: true }
  return { x: t.r.left + t.r.width / 2, y: t.r.top + t.r.height / 2, alt: svg.getAttribute('aria-label') }
}`

const tips = (page) =>
  page.evaluate(() => ({
    plot: [...document.querySelectorAll('g[aria-label="tip"]')].map((g) => g.textContent?.trim()).find(Boolean) ?? '',
    shared: document.querySelector('.ee-tip[data-show]')?.textContent?.trim() ?? '',
  }))

for (const c of CASES) {
  const ctx = await browser.newContext({ ...devices['Pixel 7'], colorScheme: process.env.SCHEME ?? 'light', ...(process.env.VH ? { viewport: { width: 412, height: Number(process.env.VH) } } : {}) })
  const page = await ctx.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto(base, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1800)
  // search is behind the top bar on phones: use the box directly
  await page.locator('#school-search').fill(c.term)
  await page.waitForTimeout(500)
  await page.locator('#search-results li button', { hasText: c.label }).first().tap()
  const aside = page.locator(`aside[aria-label="${c.aside}"]`)
  await aside.waitFor({ timeout: 30000 })
  await page.waitForTimeout(2500)
  // open the sheet fully so there is room to read charts
  const grab = aside.getByRole('button', { name: /^Panel size/ })
  for (let k = 0; k < 2 && (await aside.getAttribute('data-snap')) !== 'full'; k++) {
    await grab.tap()
    await page.waitForTimeout(350)
  }

  for (const tab of c.tabs) {
    await aside.getByRole('tab', { name: tab, exact: true }).tap()
    await aside.locator('.chart svg[role=img], ul.bars, .gb, table[aria-label], .facts, .explorer').first().waitFor({ timeout: 30000 }).catch(() => {})
    await page.waitForTimeout(1400)
    const where = `${c.kind} / ${tab}`
    checked++

    // geometry: nothing wider than its card, no sideways page scroll
    const geo = await aside.evaluate((root) => {
      const body = root.querySelector('.tabbody')
      const bad = []
      const W = window.innerWidth
      for (const card of body.querySelectorAll(':scope > .card, :scope > .span')) {
        const cr = card.getBoundingClientRect()
        if (cr.right > W + 1 || cr.left < -1) bad.push(`card "${card.querySelector('h3')?.textContent?.trim().slice(0, 30)}" leaves the screen (${Math.round(cr.left)}..${Math.round(cr.right)})`)
        for (const el of card.querySelectorAll('svg[role=img], ul, table, .gb, .legend, .swatches, [class*=swatch]')) {
          const r = el.getBoundingClientRect()
          const scroller = el.closest('.wrap')
          if (!scroller && r.right > cr.right + 1) bad.push(`${el.tagName.toLowerCase()} in "${card.querySelector('h3')?.textContent?.trim().slice(0, 30)}" overflows its card by ${Math.round(r.right - cr.right)}px`)
        }
      }
      return { bad, sideways: document.documentElement.scrollWidth > window.innerWidth + 1 }
    })
    geo.bad.forEach((m) => fail(`${where}: ${m}`))
    if (geo.sideways) fail(`${where}: page scrolls sideways`)

    // tap targets in the panel
    const small = await aside.evaluate((root) =>
      [...root.querySelectorAll('button, [role=tab], a, [role=slider]')]
        .filter((e) => e.offsetParent !== null)
        .map((e) => ({ t: (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 24), r: e.getBoundingClientRect() }))
        .filter(({ r }) => r.width < 24 || r.height < 24)
        .map(({ t, r }) => `${t || '(unlabelled)'} ${Math.round(r.width)}x${Math.round(r.height)}`),
    )
    small.forEach((m) => fail(`${where}: tap target under 24px: ${m}`))

    // tap each Plot chart
    const n = await aside.locator('.chart').count()
    for (let i = 0; i < n; i++) {
      await aside.locator('.chart').nth(i).scrollIntoViewIfNeeded()
      await page.waitForTimeout(120)
      const hit = await aside.evaluate(new Function('root', 'i', `return (${POINT})(root, i)`), i)
      checked++
      if (!hit || hit.none) {
        fail(`${where}: chart ${i} (${hit?.alt ?? '?'}) has no marks to tap`)
        continue
      }
      await page.touchscreen.tap(hit.x, hit.y)
      await page.waitForTimeout(300)
      const t = await tips(page)
      t.plot.length > 3 ? ok(`${where}: tap "${hit.alt?.slice(0, 40)}" -> ${t.plot.replace(/\s+/g, ' ').slice(0, 40)}`) : fail(`${where}: tapping chart "${hit.alt}" shows no tooltip`)
      await page.touchscreen.tap(5, 5)
    }
    // tap the other chart kinds
    for (const [name, sel] of [
      ['bar list row', 'ul.bars li'],
      ['grade bar segment', '.gb .bar i'],
      ['status strip cell', 'table[aria-label] td:not(.nowv):not(.gap)'],
    ]) {
      const els = aside.locator(sel)
      const count = await els.count()
      if (!count) continue
      const el = els.nth(Math.floor(count / 2))
      await el.scrollIntoViewIfNeeded()
      const b = await el.boundingBox()
      await page.touchscreen.tap(b.x + b.width / 2, b.y + b.height / 2)
      await page.waitForTimeout(250)
      const t = await tips(page)
      checked++
      t.shared.length > 3 ? ok(`${where}: tap ${name} -> ${t.shared.slice(0, 50)}`) : fail(`${where}: tapping ${name} shows no tooltip`)
      await page.waitForTimeout(2400) // touch tooltips fade by themselves
    }
    await aside.locator('.body').evaluate((e) => (e.scrollTop = 0))
    await page.screenshot({ path: `${out}/touch-${c.kind.replace(' ', '')}-${tab}.png` })
  }
  errors.length ? errors.forEach((e) => fail(`${c.kind}: pageerror ${e}`)) : null
  await ctx.close()
}
await browser.close()
console.log(`${checked} checks`)
console.log(bad ? 'TOUCH FAILED' : 'TOUCH PASSED')
process.exitCode = bad ? 1 : 0
