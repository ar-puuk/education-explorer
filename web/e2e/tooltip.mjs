// Visual check: chart tooltip in dark mode and the inspector tab row. node e2e/tooltip.mjs <baseUrl> <outDir>
import { chromium } from 'playwright'
const base = process.argv[2] ?? 'http://localhost:4173/'
const out = process.argv[3] ?? 'e2e/shots'
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const page = await (await browser.newContext({ viewport: { width: 1440, height: 860 }, colorScheme: 'dark' })).newPage()
await page.goto(base, { waitUntil: 'networkidle' })
await page.waitForTimeout(2000)
await page.keyboard.press('Control+k')
await page.keyboard.type('elementary')
await page.locator('#search-results li button', { hasText: 'Public school' }).first().click()
await page.waitForSelector('aside[aria-label="School details"] .card svg', { timeout: 60000 })
await page.waitForTimeout(1500)
const box = await page.locator('aside[aria-label="School details"] .card svg').first().boundingBox()
const dot = await page.locator('aside[aria-label="School details"] .card svg circle').nth(1).boundingBox()
await page.mouse.move(dot.x - 30, dot.y - 20)
await page.mouse.move(dot.x + 2, dot.y + 2, { steps: 6 })
await page.waitForTimeout(500)
await page.screenshot({ path: `${out}/tooltip-dark.png`, clip: { x: 980, y: 400, width: 460, height: 400 } })
const tabs = await page.locator('[role=tablist]').evaluate((e) => ({ sw: e.scrollWidth, cw: e.clientWidth }))
console.log('tablist', tabs)
await browser.close()
