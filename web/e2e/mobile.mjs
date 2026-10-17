// Mobile layout sanity: node e2e/mobile.mjs <baseUrl> <outDir>
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
const base = process.argv[2], out = process.argv[3]
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
const ctx = await browser.newContext({ viewport: { width: 390, height: 800 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
const page = await ctx.newPage()
await page.goto(base, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => window.__ee?.controller?.map?.loaded(), null, { timeout: 40000 })
await page.waitForTimeout(1500)
await page.screenshot({ path: `${out}/m1-home.png` })
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
console.log(overflow ? 'FAIL: horizontal page scroll' : 'ok: no horizontal page scroll')
await page.locator('#school-search').fill('Provo High')
await page.locator('#search-results li button').first().click()
await page.waitForSelector('aside[aria-label="School details"] svg', { timeout: 60000 })
await page.waitForTimeout(800)
await page.screenshot({ path: `${out}/m2-detail.png` })
await browser.close()
