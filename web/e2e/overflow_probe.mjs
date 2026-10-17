// Lists the elements that stick out past the viewport on the methodology page at phone width.
import { chromium } from 'playwright'
const base = (process.argv[2] ?? 'http://localhost:4173/').replace(/\/?$/, '/')
const browser = await chromium.launch()
const page = await (await browser.newContext({ viewport: { width: 390, height: 800 } })).newPage()
await page.goto(base + 'methodology.html', { waitUntil: 'networkidle' })
await page.waitForSelector('#versions li.cv')
const w = await page.evaluate(() => innerWidth)
const bad = await page.evaluate((w) => {
  const out = []
  for (const e of document.querySelectorAll('body *')) {
    const r = e.getBoundingClientRect()
    if (r.right > w + 1 && !e.closest('.scroll') && !e.closest('.code') && getComputedStyle(e).position !== 'absolute') out.push(`${e.tagName.toLowerCase()}${e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : ''}${e.id ? '#' + e.id : ''} right=${Math.round(r.right)} w=${Math.round(r.width)}`)
  }
  return out.slice(0, 20)
}, w)
console.log('viewport', w, 'scrollWidth', await page.evaluate(() => document.documentElement.scrollWidth))
console.log(bad.join('\n'))
await browser.close()
