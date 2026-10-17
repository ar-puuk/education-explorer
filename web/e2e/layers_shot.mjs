// Screenshot of the Layers drawer with and without a colour-by choice. node e2e/layers_shot.mjs <baseUrl> <outDir>
import { chromium } from 'playwright'
const base = process.argv[2] ?? 'http://localhost:4173/'
const out = process.argv[3] ?? 'e2e/shots'
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const page = await (await browser.newContext({ viewport: { width: 1000, height: 760 } })).newPage()
await page.goto(base, { waitUntil: 'networkidle' })
await page.waitForTimeout(2000)
const group = page.getByRole('group', { name: 'Colour public schools by' })
if (!(await group.isVisible())) await page.getByRole('button', { name: 'Layers', exact: true }).click()
await page.screenshot({ path: `${out}/layers-none.png`, clip: { x: 0, y: 40, width: 420, height: 560 } })
await group.getByRole('button', { name: 'Locale', exact: true }).click()
await page.waitForTimeout(500)
await page.screenshot({ path: `${out}/layers-locale.png`, clip: { x: 0, y: 40, width: 420, height: 640 } })
await browser.close()
