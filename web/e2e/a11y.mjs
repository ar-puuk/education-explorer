// Accessibility scan (axe-core, WCAG 2.x A/AA) in light and dark: node e2e/a11y.mjs <baseUrl>
import { chromium } from 'playwright'
import AxeBuilder from '@axe-core/playwright'

const base = process.argv[2] ?? 'http://localhost:4173/'
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
let failures = 0
for (const scheme of ['light', 'dark']) {
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 820 }, colorScheme: scheme })
  const page = await ctx.newPage()
  await page.goto(base, { waitUntil: 'domcontentloaded' })
  await page.waitForFunction(() => window.__ee?.controller?.map?.loaded(), null, { timeout: 40000 })
  const scan = async (label) => {
    const r = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).exclude('.maplibregl-canvas').analyze()
    const v = r.violations
    console.log(`${scheme} / ${label}: ${v.length} violation(s)`)
    for (const x of v) {
      failures++
      console.log(`  [${x.impact}] ${x.id}: ${x.help} (${x.nodes.length} nodes)`)
      for (const n of x.nodes.slice(0, 3)) console.log('     ', n.target.join(' '), '|', (n.failureSummary || '').split('\n')[1] ?? '')
    }
  }
  await scan('home')
  await page.locator('#school-search').fill('high')
  await page.locator('#search-results li button', { hasText: 'Public school' }).first().click()
  await page.waitForSelector('aside[aria-label="School details"] .card svg', { timeout: 60000 })
  await page.waitForTimeout(500)
  await scan('school panel')
  await page.getByRole('tab', { name: 'Trends' }).click()
  await page.waitForTimeout(800)
  await scan('school trends tab')
  await page.getByRole('button', { name: 'Expand panel' }).click()
  await page.waitForTimeout(500)
  await scan('school panel expanded')
  await page.getByRole('button', { name: 'Shrink panel' }).click()
  await page.getByRole('button', { name: 'Close details' }).click()
  if (!(await page.getByRole('radiogroup', { name: 'Basemap style' }).isVisible())) await page.getByRole('button', { name: 'Basemap & appearance' }).click()
  await scan('basemap drawer')
  await page.getByRole('button', { name: 'Filters', exact: true }).click()
  await scan('filters drawer')
  await page.getByRole('button', { name: 'Open data tables' }).click()
  await page.waitForSelector('[role=dialog] tbody tr')
  await scan('table dialog')
  await ctx.close()
}
await browser.close()
console.log(failures ? `A11Y: ${failures} violation group(s)` : 'A11Y: clean')
process.exitCode = failures ? 1 : 0
