// Visual check helper: node e2e/look.mjs <baseUrl> <outDir>
// Takes screenshots of the shell in both themes, with a school open, the basemap drawer, and a phone viewport.
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'

const base = process.argv[2] ?? 'http://localhost:5173/'
const out = process.argv[3] ?? 'e2e/shots'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const errors = []

async function open(scheme, viewport) {
  const ctx = await browser.newContext({ viewport, colorScheme: scheme })
  const page = await ctx.newPage()
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => {
    if (m.type() === 'error' && !/favicon|Failed to load resource/i.test(m.text())) errors.push('console: ' + m.text().slice(0, 200))
  })
  await page.goto(base, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2500)
  return page
}

for (const scheme of ['light', 'dark']) {
  const page = await open(scheme, { width: 1440, height: 860 })
  await page.screenshot({ path: `${out}/${scheme}-1-home.png` })
  await page.getByRole('button', { name: 'Basemap & appearance' }).click()
  await page.waitForTimeout(500)
  await page.screenshot({ path: `${out}/${scheme}-2-basemap.png` })
  await page.getByRole('button', { name: 'Filters' }).click()
  await page.getByRole('button', { name: 'Layers' }).click()
  // open the biggest public school via the search box
  await page.keyboard.press('Control+k')
  await page.keyboard.type('elementary')
  await page.waitForTimeout(400)
  await page.locator('#search-results li button', { hasText: 'Public school' }).first().click()
  await page.waitForTimeout(2500)
  await page.screenshot({ path: `${out}/${scheme}-3-inspector.png` })
  await page.getByRole('tab', { name: 'Trends' }).click()
  await page.waitForTimeout(1200)
  await page.screenshot({ path: `${out}/${scheme}-4-trends.png` })
  await page.getByRole('button', { name: 'Expand panel' }).click()
  await page.getByRole('tab', { name: 'Overview' }).click()
  await page.waitForTimeout(1200)
  await page.screenshot({ path: `${out}/${scheme}-5-wide.png` })
  await page.context().close()
}
const phone = await open('light', { width: 400, height: 800 })
await phone.screenshot({ path: `${out}/phone-1-home.png` })
await phone.keyboard.press('Control+k')
await phone.keyboard.type('elementary')
await phone.waitForTimeout(400)
await phone.locator('#search-results li button', { hasText: 'Public school' }).first().click()
await phone.waitForTimeout(2500)
await phone.screenshot({ path: `${out}/phone-2-inspector.png` })
console.log(errors.length ? errors.join('\n') : 'no errors')
await browser.close()
