// Compare tray (desktop) and bottom-sheet snap points (phone). node e2e/tray_sheet.mjs <baseUrl> <outDir>
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
const base = process.argv[2] ?? 'http://localhost:4173/'
const out = process.argv[3] ?? 'e2e/shots'
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] })
let bad = 0
const ok = (m) => console.log('ok:', m)
const fail = (m) => {
  console.error('FAIL:', m)
  bad++
}

async function pickFirst(page, term) {
  await page.keyboard.press('Control+k')
  await page.keyboard.type(term)
  await page.locator('#search-results li button').first().click()
  await page.waitForSelector('aside[aria-label="School details"] .card', { timeout: 60000 }).catch(() => {})
}

// ---------------------------------------------------------------- desktop tray
{
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 860 } })).newPage()
  await page.goto(base, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  const tray = page.getByRole('region', { name: 'Places to compare' })
  ;(await tray.count()) === 0 ? ok('tray hidden when nothing is queued') : fail('tray visible with empty compare list')
  await pickFirst(page, 'elementary')
  await page.getByRole('button', { name: '+ Compare' }).click()
  await tray.waitFor({ timeout: 5000 })
  ok('tray appears after adding a place')
  await pickFirst(page, 'high')
  await page.getByRole('button', { name: '+ Compare' }).click()
  const n = await tray.locator('li').count()
  n === 2 ? ok('tray lists two places') : fail('tray items: ' + n)
  await page.screenshot({ path: `${out}/tray-desktop.png` })
  await tray.getByRole('button', { name: /^Remove / }).first().click()
  ;(await tray.locator('li').count()) === 1 ? ok('chip remove works') : fail('remove did not shrink the tray')
  await tray.getByRole('button', { name: 'Open' }).click()
  await page.waitForSelector('[role=dialog][aria-label="Compare places"]', { timeout: 10000 })
  ok('tray button opens the compare dialog')
  await page.getByRole('button', { name: 'Close compare' }).click()
  await tray.getByRole('button', { name: 'Clear' }).click()
  ;(await tray.count()) === 0 ? ok('Clear empties and hides the tray') : fail('tray still visible after Clear')
  await page.context().close()
}

// ---------------------------------------------------------------- phone sheet
{
  const page = await (await browser.newContext({ viewport: { width: 390, height: 800 }, deviceScaleFactor: 2 })).newPage()
  await page.goto(base, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  await pickFirst(page, 'elementary')
  const sheet = page.locator('aside[aria-label="School details"]')
  const grab = sheet.getByRole('button', { name: /^Panel size/ })
  const snap = () => sheet.getAttribute('data-snap')
  const h = async () => Math.round((await sheet.boundingBox()).height)
  const hHalf = await h()
  ;(await snap()) === 'half' ? ok(`opens at half (${hHalf}px)`) : fail('initial snap ' + (await snap()))
  await page.screenshot({ path: `${out}/sheet-half.png` })
  await grab.click()
  await page.waitForTimeout(400)
  const hFull = await h()
  ;(await snap()) === 'full' && hFull > hHalf + 100 ? ok(`tap -> full (${hFull}px)`) : fail(`tap: ${await snap()} ${hFull}`)
  await page.screenshot({ path: `${out}/sheet-full.png` })
  await grab.click()
  await page.waitForTimeout(400)
  const hPeek = await h()
  ;(await snap()) === 'peek' && hPeek < hHalf - 100 ? ok(`tap -> peek (${hPeek}px)`) : fail(`tap: ${await snap()} ${hPeek}`)
  await page.screenshot({ path: `${out}/sheet-peek.png` })
  // drag up from peek by ~half the screen -> half or full
  const b = await grab.boundingBox()
  await page.mouse.move(b.x + b.width / 2, b.y + 8)
  await page.mouse.down()
  await page.mouse.move(b.x + b.width / 2, b.y - 260, { steps: 10 })
  await page.mouse.up()
  await page.waitForTimeout(400)
  ;(await snap()) !== 'peek' ? ok('drag up leaves peek -> ' + (await snap())) : fail('drag up stayed at peek')
  // keyboard
  await grab.focus()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('ArrowDown')
  ;(await snap()) === 'peek' ? ok('ArrowDown steps down to peek') : fail('keyboard snap ' + (await snap()))
  // drag far below peek -> dismiss
  const b2 = await grab.boundingBox()
  await page.mouse.move(b2.x + b2.width / 2, b2.y + 8)
  await page.mouse.down()
  await page.mouse.move(b2.x + b2.width / 2, b2.y + 200, { steps: 10 })
  await page.mouse.up()
  await page.waitForTimeout(400)
  ;(await sheet.count()) === 0 ? ok('dragging well below peek dismisses the panel') : fail('sheet still open after dismiss drag')
  // tray on phone sits above the timeline and lifts the sheet
  await pickFirst(page, 'elementary')
  await page.getByRole('button', { name: '+ Compare' }).click()
  await page.waitForTimeout(400)
  const tb = await page.getByRole('region', { name: 'Places to compare' }).boundingBox()
  const sb = await sheet.boundingBox()
  sb.y + sb.height <= tb.y + 1 ? ok('phone: sheet sits above the compare tray') : fail(`overlap: sheet bottom ${sb.y + sb.height}, tray top ${tb.y}`)
  await page.screenshot({ path: `${out}/tray-phone.png` })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
  overflow ? fail('horizontal page scroll on phone') : ok('no horizontal scroll with tray and sheet')
}
await browser.close()
console.log(bad ? 'TRAY/SHEET FAILED' : 'TRAY/SHEET PASSED')
process.exitCode = bad ? 1 : 0
