// Run only against an already running real local server. Does not start a scan.
import { chromium } from '../frontend/node_modules/@playwright/test/index.mjs'
import fs from 'node:fs'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const errors = []
page.on('pageerror', error => errors.push(error.message))
await page.goto('http://127.0.0.1:8765')
await page.locator('.opportunity').first().waitFor()
await page.screenshot({ path: 'data/live-desktop.png', fullPage: true })
await page.getByRole('button', { name: 'Dark appearance' }).click()
await page.screenshot({ path: 'data/live-dark.png', fullPage: true, animations: 'disabled' })
await page.setViewportSize({ width: 390, height: 844 })
await page.screenshot({ path: 'data/live-mobile-dark.png', fullPage: true, animations: 'disabled' })
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
const count = await page.locator('.opportunity').count()
await page.setViewportSize({ width: 1440, height: 1000 })
await page.getByRole('navigation').getByRole('button', { name: 'Digest', exact: false }).click()
await page.locator('.digest-stats').waitFor()
await page.screenshot({ path: 'data/live-digest.png', animations: 'disabled' })
await page.getByRole('navigation').getByRole('button', { name: 'Tracker', exact: false }).click()
await page.getByRole('heading', { name: 'Turn discoveries into next steps.' }).waitFor()
await page.screenshot({ path: 'data/live-tracker.png', animations: 'disabled' })
await page.getByRole('navigation').getByRole('button', { name: 'Live discovery', exact: false }).click()
await page.getByRole('heading', { name: 'A radar that keeps exploring.' }).waitFor()
await page.screenshot({ path: 'data/live-discovery-desktop.png', animations: 'disabled', fullPage: true })
await page.setViewportSize({ width: 390, height: 844 })
await page.screenshot({ path: 'data/live-discovery-mobile.png', animations: 'disabled', fullPage: true })
const discoveryOverflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
await browser.close()
const result = { displayedCards: count, pageErrors: errors, mobileOverflow: overflow, discoveryOverflow }
fs.writeFileSync('data/visual-smoke.json', JSON.stringify(result, null, 2))
console.log(JSON.stringify(result))
if (errors.length || overflow || discoveryOverflow) process.exitCode = 1
