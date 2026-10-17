// Visual check of MapLibre attribution and scale in both themes. node e2e/attrib.mjs <baseUrl> <outDir>
import { chromium } from 'playwright'
const base = process.argv[2] ?? 'http://localhost:4173/'
const out = process.argv[3] ?? 'e2e/shots'
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
for (const scheme of ['light', 'dark']) {
  const page = await (await browser.newContext({ viewport: { width: 1000, height: 700 }, colorScheme: scheme })).newPage()
  await page.goto(base, { waitUntil: 'networkidle' })
  await page.waitForTimeout(2500)
  const clip = { x: 500, y: 560, width: 500, height: 80 }
  await page.screenshot({ path: `${out}/attrib-${scheme}-1.png`, clip })
  await page.locator('.maplibregl-ctrl-attrib-button').click()
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${out}/attrib-${scheme}-2.png`, clip })
}
await browser.close()
