// Viewport screenshots of each section of the methodology page. node e2e/method_shots.mjs <baseUrl> <outDir> [light|dark]
import { chromium } from 'playwright'
const base = (process.argv[2] ?? 'http://localhost:4173/').replace(/\/?$/, '/')
const out = process.argv[3] ?? 'e2e/shots'
const scheme = process.argv[4] ?? 'light'
const browser = await chromium.launch()
const page = await (await browser.newContext({ viewport: { width: 1360, height: 900 }, colorScheme: scheme })).newPage()
await page.goto(base + 'methodology.html', { waitUntil: 'networkidle' })
await page.waitForSelector('#versions li.cv')
await page.locator('#expand').click()
for (const id of ['start', 'officials', 'sources', 'charts', 'terms', 'numbers', 'limits', 'coverage', 'technical', 'cite']) {
  await page.locator('#' + id).scrollIntoViewIfNeeded()
  await page.evaluate((i) => document.getElementById(i).scrollIntoView({ block: 'start' }), id)
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${out}/msec-${scheme}-${id}.png` })
}
await browser.close()
