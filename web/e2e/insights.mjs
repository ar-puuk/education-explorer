// Chart tabs for every kind of place: node e2e/insights.mjs <baseUrl> <outDir>
// Opens a college, a public school, a private school and a district, visits each new tab in both themes,
// checks that charts drew (svg or list), that nothing threw, and saves screenshots.
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const base = process.argv[2] ?? 'http://localhost:5173/'
const out = process.argv[3] ?? 'e2e/shots'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
let bad = 0
const ok = (m) => console.log('ok:', m)
const fail = (m) => {
  console.error('FAIL:', m)
  bad++
}
const errors = []

const CASES = [
  { kind: 'College', term: 'university', label: /College/, aside: 'College details', tabs: ['Overview', 'Students', 'Outcomes', 'Costs'], min: { Overview: 2, Students: 4, Outcomes: 2, Costs: 4 } },
  { kind: 'Public school', term: 'elementary', label: /Public school/, aside: 'School details', tabs: ['Students', 'Programs'], min: { Students: 2, Programs: 1 } },
  { kind: 'Private school', term: 'academy', label: /Private school/, aside: 'Private school details', tabs: ['Students'], min: { Students: 1 } },
  { kind: 'District', term: 'district', label: /district/i, aside: 'District details', tabs: ['Students', 'Money'], min: { Students: 1, Money: 1 } },
]

for (const scheme of ['light', 'dark']) {
  for (const c of CASES) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: Number(process.env.VH ?? 900) }, colorScheme: scheme })
    const page = await ctx.newPage()
    page.on('pageerror', (e) => errors.push(`${c.kind}: pageerror ${e.message}`))
    page.on('console', (m) => {
      if (m.type() === 'error' && !/favicon|Failed to load resource/i.test(m.text())) errors.push(`${c.kind}: console ${m.text().slice(0, 160)}`)
    })
    await page.goto(base, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1800)
    await page.keyboard.press('Control+k')
    await page.keyboard.type(c.term)
    await page.waitForTimeout(500)
    const hit = page.locator('#search-results li button', { hasText: c.label }).first()
    if (!(await hit.count())) {
      fail(`${c.kind}: no search hit for "${c.term}"`)
      await ctx.close()
      continue
    }
    await hit.click()
    const aside = page.locator(`aside[aria-label="${c.aside}"]`)
    await aside.waitFor({ timeout: 30000 })
    await page.waitForTimeout(2500)
    for (const t of c.tabs) {
      await aside.getByRole('tab', { name: t, exact: true }).click()
      await page.waitForTimeout(2200)
      await aside.locator('.chart svg[role=img], ul.bars, table[aria-label]').first().waitFor({ timeout: 30000 }).catch(() => {})
      await page.waitForTimeout(800)
      const charts = await aside.locator('.chart svg[role=img], ul.bars, table[aria-label]').count()
      charts >= c.min[t] ? ok(`${scheme} ${c.kind} ${t}: ${charts} charts`) : fail(`${scheme} ${c.kind} ${t}: only ${charts} charts (want ${c.min[t]})`)
      const empties = await aside.locator('.muted').allTextContents()
      if (empties.length) console.log(`   (${t}) empty states:`, empties.map((x) => x.trim().slice(0, 50)).join(' | '))
      await page.screenshot({ path: `${out}/ins-${scheme}-${c.kind.replace(' ', '')}-${t}.png` })
    }
    await ctx.close()
  }
}
errors.length ? errors.forEach((e) => fail(e)) : ok('no console errors')
await browser.close()
console.log(bad ? 'INSIGHTS FAILED' : 'INSIGHTS PASSED')
process.exitCode = bad ? 1 : 0
