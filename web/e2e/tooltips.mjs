// Every chart must have a working tooltip, and expanded cards must fill the row.
// node e2e/tooltips.mjs <baseUrl> <outDir>
// Visits each chart tab for a college, public school, private school and district, hovers every chart
// (Plot marks, bars, grade bars, status strips, the timeline) and checks that a tooltip with text appears.
import { chromium } from 'playwright'
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

const CASES = [
  { kind: 'College', term: 'university', label: /College/, aside: 'College details', tabs: ['Overview', 'Students', 'Outcomes', 'Costs'] },
  { kind: 'Public school', term: 'elementary', label: /Public school/, aside: 'School details', tabs: ['Overview', 'Students', 'Programs', 'Trends'] },
  { kind: 'Private school', term: 'academy', label: /Private school/, aside: 'Private school details', tabs: ['Overview', 'Students', 'Trends', 'Details'] },
  { kind: 'District', term: 'district', label: /district/i, aside: 'District details', tabs: ['Overview', 'Students', 'Money', 'Trends'] },
]

/** Screen point to hover for chart `i` inside the aside, by chart type. */
const TARGETS = `(root, i) => {
  const c = root.querySelectorAll('.chart')[i]
  const svg = [...c.querySelectorAll('svg')].find((s) => s.getAttribute('role') === 'img')
  const pick = (els) => els.map((e) => ({ e, r: e.getBoundingClientRect() })).filter(({ r }) => r.width > 2 && r.height > 2)
  const dots = pick([...svg.querySelectorAll('circle')])
  const bars = pick([...svg.querySelectorAll('rect')]).filter(({ r }) => r.width < svg.getBoundingClientRect().width * 0.9 && r.height < svg.getBoundingClientRect().height * 0.95)
  const t = dots[Math.floor(dots.length / 2)] ?? bars[Math.floor(bars.length / 2)]
  if (!t) return null
  return { x: t.r.left + t.r.width / 2, y: t.r.top + t.r.height / 2, alt: svg.getAttribute('aria-label') }
}`

async function tipText(page) {
  return page.evaluate(() => {
    const plot = [...document.querySelectorAll('g[aria-label="tip"]')].map((g) => g.textContent?.trim()).find(Boolean)
    const shared = document.querySelector('.ee-tip[data-show]')
    return { plot: plot ?? '', shared: shared?.textContent?.trim() ?? '' }
  })
}

for (const c of CASES) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'dark' })
  const page = await ctx.newPage()
  await page.goto(base, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1800)
  await page.keyboard.press('Control+k')
  await page.keyboard.type(c.term)
  await page.waitForTimeout(500)
  await page.locator('#search-results li button', { hasText: c.label }).first().click()
  const aside = page.locator(`aside[aria-label="${c.aside}"]`)
  await aside.waitFor({ timeout: 30000 })
  await page.waitForTimeout(2500)

  // the timeline histogram
  const track = page.locator('[role=slider][aria-label="School year"]')
  if (c.kind === 'College') {
    const tb = await track.boundingBox()
    await page.mouse.move(tb.x + tb.width * 0.4, tb.y + tb.height / 2)
    await page.mouse.move(tb.x + tb.width * 0.41, tb.y + tb.height / 2, { steps: 3 })
    await page.waitForTimeout(200)
    const t = await tipText(page)
    checked++
    t.shared.length > 8 ? console.log('ok: timeline tip:', t.shared) : fail('timeline has no tooltip')
    await page.mouse.move(5, 5)
  }

  for (const tab of c.tabs) {
    await aside.getByRole('tab', { name: tab, exact: true }).click()
    await aside.locator('.chart svg[role=img], ul.bars, .gb, table[aria-label]').first().waitFor({ timeout: 30000 }).catch(() => {})
    await page.waitForTimeout(1500)
    const where = `${c.kind} / ${tab}`

    // Plot charts
    const n = await aside.locator('.chart').count()
    for (let i = 0; i < n; i++) {
      const hit = await aside.evaluate(new Function('root', 'i', `return (${TARGETS})(root, i)`), i)
      if (!hit) {
        fail(`${where}: chart ${i} has no marks to hover`)
        continue
      }
      await aside.locator('.chart').nth(i).scrollIntoViewIfNeeded()
      const again = await aside.evaluate(new Function('root', 'i', `return (${TARGETS})(root, i)`), i)
      await page.mouse.move(again.x - 25, again.y - 18)
      await page.mouse.move(again.x, again.y, { steps: 6 })
      await page.waitForTimeout(250)
      const t = await tipText(page)
      checked++
      if (t.plot.length > 3) console.log(`ok: ${where}: "${again.alt?.slice(0, 48)}" -> ${t.plot.replace(/\s+/g, ' ').slice(0, 50)}`)
      else fail(`${where}: no tooltip on chart "${again.alt}"`)
      await page.mouse.move(5, 5)
    }

    // shared-tooltip targets: bar rows, grade bars, strip cells
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
      await page.mouse.move(b.x + b.width / 2 - 3, b.y + b.height / 2)
      await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 3 })
      await page.waitForTimeout(150)
      const t = await tipText(page)
      checked++
      t.shared.length > 3 ? console.log(`ok: ${where}: ${name} -> ${t.shared.slice(0, 60)}`) : fail(`${where}: no tooltip on ${name}`)
      await page.mouse.move(5, 5)
    }
  }

  // expanded panel: every card either spans the row or shares it with another card
  await page.getByRole('button', { name: 'Expand panel' }).click()
  await page.waitForTimeout(500)
  for (const tab of c.tabs) {
    await aside.getByRole('tab', { name: tab, exact: true }).click()
    await page.waitForTimeout(1200)
    const orphans = await aside.evaluate((root) => {
      const body = root.querySelector('.tabbody')
      const cards = [...body.querySelectorAll(':scope > .card')]
      const W = body.getBoundingClientRect().width
      return cards
        .map((el) => ({ el, r: el.getBoundingClientRect() }))
        .filter(({ el, r }) => r.width < W * 0.9 && !cards.some((o) => o !== el && Math.abs(o.getBoundingClientRect().top - r.top) < 4))
        .map(({ el }) => el.querySelector('h3')?.textContent?.trim().slice(0, 40))
    })
    checked++
    orphans.length ? fail(`${c.kind} / ${tab} (expanded): half-width card with no neighbour: ${orphans.join(', ')}`) : console.log(`ok: ${c.kind} / ${tab} expanded layout fills the width`)
  }
  await ctx.close()
}
await browser.close()
console.log(`${checked} checks`)
console.log(bad ? 'TOOLTIPS FAILED' : 'TOOLTIPS PASSED')
process.exitCode = bad ? 1 : 0
