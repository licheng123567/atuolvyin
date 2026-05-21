import { chromium, devices } from '@playwright/test';
import fs from 'fs';

const jwt = fs.readFileSync('/tmp/jwt.txt', 'utf8').trim();
const backend = 'http://192.168.31.242:18000';
const frontend = 'http://192.168.31.242:5173';

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  ...devices['Pixel 5'],
  // Pretend we're an Android WebView
  userAgent: 'Mozilla/5.0 (Linux; Android 9; Redmi Note 4X) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.114 Mobile Safari/537.36',
});

// Inject AndroidBridge stub BEFORE any page JS runs (mimics native @JavascriptInterface)
await ctx.addInitScript((args) => {
  window.AndroidBridge = {
    getJwt: () => args.jwt,
    getBackendUrl: () => args.backend,
    getCapability: () => JSON.stringify({ capability: 'realtime', rom: 'TestROM', guidance: 'OK', checked_at: new Date().toISOString() }),
    dialCase: (json) => console.log('[Bridge] dialCase', json),
    scanQr: () => console.log('[Bridge] scanQr'),
    openCaseDetail: (id) => console.log('[Bridge] openCaseDetail', id),
    notifyAuthError: () => console.log('[Bridge] notifyAuthError'),
  };
  window.__JWT__ = args.jwt;
  window.__BACKEND__ = args.backend;
}, { jwt, backend });

const page = await ctx.newPage();

const errors = [];
const failedRequests = [];
const consoleMsgs = [];

page.on('console', (msg) => {
  consoleMsgs.push(`[${msg.type()}] ${msg.text()}`);
});
page.on('pageerror', (err) => {
  errors.push(`PAGEERROR: ${err.message}\n${err.stack}`);
});
page.on('requestfailed', (req) => {
  failedRequests.push(`FAIL ${req.method()} ${req.url()} — ${req.failure()?.errorText}`);
});
page.on('response', async (resp) => {
  const status = resp.status();
  const url = resp.url();
  if (status >= 400) {
    failedRequests.push(`${status} ${resp.request().method()} ${url}`);
  }
});

const target = `${frontend}/app/home`;
console.log(`Loading: ${target}\n`);
try {
  await page.goto(target, { waitUntil: 'networkidle', timeout: 10000 });
} catch (e) {
  console.log('goto error:', e.message);
}

await page.waitForTimeout(2000);

// Capture DOM
const root = await page.locator('#root').innerHTML();
const url = page.url();
console.log('Final URL:', url);
console.log('\n=== ROOT innerHTML (first 800 chars) ===');
console.log(root.slice(0, 800));

console.log('\n=== Console msgs ===');
consoleMsgs.slice(-20).forEach(m => console.log(m));
console.log('\n=== Page errors ===');
errors.forEach(e => console.log(e));
console.log('\n=== Failed requests ===');
failedRequests.slice(0, 20).forEach(r => console.log(r));

await page.screenshot({ path: '/tmp/webview-sim.png' });
console.log('\nScreenshot saved: /tmp/webview-sim.png');

await browser.close();
