import { chromium, devices } from '@playwright/test';

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  ...devices['Pixel 5'],
  userAgent: 'Mozilla/5.0 (Linux; Android 6.0; Redmi Note 4X) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/53 Mobile Safari/537.36',
});

// Stub AndroidBridge with a fake JWT
const jwt = 'fake.jwt.token';
const backend = 'http://192.168.31.242:18000';
await ctx.addInitScript((args) => {
  window.AndroidBridge = {
    getJwt: () => args.jwt,
    getBackendUrl: () => args.backend,
    getCapability: () => JSON.stringify({ recordingAvailable: true, mode: 'system', reason: 'ok' }),
    pingBackend: () => true,
  };
}, { jwt, backend });

const page = await ctx.newPage();
const errs = [];
page.on('pageerror', (e) => errs.push(`ERR ${e.message}`));
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(`[${m.type()}] ${m.text().slice(0,160)}`); });

console.log('Loading prod bundle from 4173...');
try {
  await page.goto('http://192.168.31.242:4173/app/home', { waitUntil: 'load', timeout: 10000 });
} catch (e) { console.log('goto err:', e.message); }
await page.waitForTimeout(2000);

console.log('URL:', page.url());
const root = await page.locator('#root').innerHTML();
console.log('Root len:', root.length);
console.log('Root preview:', root.slice(0, 400));
console.log('\n--- Errors ---');
errs.slice(0, 10).forEach(e => console.log(e));

await page.screenshot({ path: '/tmp/prod-bundle.png', fullPage: true });
await browser.close();
