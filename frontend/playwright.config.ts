import { defineConfig, devices } from "@playwright/test";

// E2E 跑在专属的「独立后端 + 独立前端」上，不与开发栈（:5173 / :18000）抢资源：
//   - 后端 :18100 —— 非 --reload 模式 uvicorn。dev 的 --reload 在 19min 长跑压测下会
//     明显变慢，导致 networkidle / 渲染超时类 flaky；非 reload 模式稳定。
//   - 前端 :5273 —— `--mode e2e` 走 .env.e2e，VITE_API_BASE 指向 :18100。
// 前置：docker 的 postgres/redis 已起、DB 已迁移 + seed（见 docs/E2E_SMOKE.md）。
// playwright 会自动拉起这两个 server；本地若已手动起好同端口实例则复用。
const E2E_BACKEND_PORT = 18100;
const E2E_FRONTEND_PORT = 5273;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false, // 单线程便于排查
  forbidOnly: !!process.env.CI,
  // Sprint 15.1 多设备踢出在并发登录时偶发 race；2 次 retry 吸收抖动
  retries: 2,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    baseURL: process.env.VITE_BASE_URL ?? `http://localhost:${E2E_FRONTEND_PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: [
    {
      // 独立 e2e 后端：非 --reload，专属端口，连开发用的 docker postgres(:25432)
      command: `python3.12 -m uvicorn app.main:app --host 127.0.0.1 --port ${E2E_BACKEND_PORT}`,
      cwd: "../poc/backend",
      url: `http://127.0.0.1:${E2E_BACKEND_PORT}/api/openapi.json`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      stdout: "ignore",
      stderr: "pipe",
    },
    {
      // 独立 e2e 前端：--mode e2e 让 VITE_API_BASE 走 .env.e2e → :18100
      command: `npm run dev -- --port ${E2E_FRONTEND_PORT} --strictPort --mode e2e`,
      url: `http://localhost:${E2E_FRONTEND_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
