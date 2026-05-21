import { chromium, devices } from '@playwright/test';

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  ...devices['Pixel 5'],
  userAgent: 'Mozilla/5.0 (Linux; Android 6.0; Redmi Note 4X) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36',
});

const page = await ctx.newPage();
const errs = [];
const reqFails = [];
page.on('pageerror', (e) => errs.push(`ERR ${e.message}\n${e.stack?.split('\n').slice(0,3).join('\n')}`));
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errs.push(`[${m.type()}] ${m.text().slice(0,200)}`); });
page.on('response', (r) => { if (r.status() >= 400) reqFails.push(`${r.status()} ${r.url().slice(0,120)}`); });

console.log('Loading without AndroidBridge (mobile browser scenario)...');
try {
  await page.goto('http://192.168.31.242:5173/app/home', { waitUntil: 'networkidle', timeout: 8000 });
} catch (e) { console.log('goto err:', e.message); }
await page.waitForTimeout(1500);

console.log('Final URL:', page.url());
const root = await page.locator('#root').innerHTML();
console.log('Root len:', root.length);
console.log('Root preview:', root.slice(0, 400));
console.log('\n--- Errors ---');
errs.slice(0, 10).forEach(e => console.log(e));
console.log('\n--- Failed responses ---');
reqFails.slice(0, 5).forEach(r => console.log(r));

await page.screenshot({ path: '/tmp/nobridge.png' });
await browser.close();
