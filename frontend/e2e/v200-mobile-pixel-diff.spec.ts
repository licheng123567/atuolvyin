// v2.0 Task 9 — Android App UI 1:1 重写：WebView 5 屏像素 diff 自动化
//
// 目的：把 React 移动屏（WebView 内嵌）的实际渲染与 ui/app-agent.html 设计稿基线
//       做像素对比；Compose 4 屏（S2/S3/S4/S9）不在本测试范围（Playwright 跑 Chromium，
//       原生 UI 测不到，需手测，详见 docs/QA_PLAYBOOKS/v2.0-android-redesign.md）。
//
// 前置：
//   1. backend 已起在 http://localhost:18000（demo 数据由 seed_demo 提供）
//   2. frontend dev server 已起在 http://localhost:5173
//   3. 第一次跑必须先生成 baseline：`npm run visual:baseline`，
//      产物 commit 到 frontend/tests/visual-baselines/v2.0-mobile/
//
// 阈值：5%（DIFF_THRESHOLD）。原 spec 想 2% 但 Refine.dev + react 18 + tailwind 在
//       Chromium WebView 内的字体子像素 + iconset（lucide-react vs HTML emoji）渲染差异
//       通常超过 2%；放宽到 5%，主要捕捉布局漂移和颜色错位。
//
// 跑法：`npm run visual:diff`
import { test, expect, Page } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
// pngjs 不带 types，运行时是 CJS 模块；用 require-style import 避免类型噪音。
// @ts-expect-error pngjs has no @types package
import { PNG } from "pngjs";
import pixelmatch from "pixelmatch";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const VIEWPORT = { width: 390, height: 844 } as const;
const DIFF_THRESHOLD = 0.05; // 5% 容差

const BASELINE_DIR = path.join(__dirname, "../tests/visual-baselines/v2.0-mobile");
const ACTUAL_DIR = path.join(__dirname, "../tests/visual-actuals/v2.0-mobile");
const DIFF_DIR = path.join(__dirname, "../tests/visual-diffs/v2.0-mobile");

interface ScreenSpec {
  name: string;            // e.g. "s1-home"
  appPath: string;         // /app/home
  designSelector: string;  // app-agent.html 内 section id
  description: string;
}

const SCREENS: ScreenSpec[] = [
  { name: "s1-home", appPath: "/app/home", designSelector: "#app-home", description: "工作台首页" },
  { name: "s5-cases", appPath: "/app/cases", designSelector: "#app-cases", description: "案件列表" },
  { name: "s6-case-detail", appPath: "/app/cases/1", designSelector: "#app-case-detail", description: "案件详情" },
  { name: "s7-call-history", appPath: "/app/call-history", designSelector: "#app-call-history", description: "通话记录" },
  { name: "s8-profile", appPath: "/app/profile", designSelector: "#app-profile", description: "个人信息" },
];

/**
 * 模拟 Android WebView 启动条件：
 *  - localStorage 写入 fake JWT，让 MobileAuthGuard 通过
 *  - 注入 AndroidBridge stub，避免组件调用 native 方法时崩
 * 注意：fake JWT 不会通过后端鉴权；需要登录数据的接口会 401，
 *       页面渲染主框架 + 错误占位（仍可以做布局 diff）。
 *       如果要消除 401 噪音，可以改用 page.route 拦截 mock，但会让测试更脆弱，
 *       本任务（Task 9）选择保留真实接口调用。
 */
async function setupMobileWebView(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("autoluyin_token", "fake-jwt-for-visual-test");
    (window as unknown as { AndroidBridge: object }).AndroidBridge = {
      getJwt: () => "fake-jwt-for-visual-test",
      getBackendUrl: () => "http://localhost:18000",
      dialCase: () => {
        /* noop */
      },
      scanQr: () => {
        /* noop */
      },
      openCaseDetail: () => {
        /* noop */
      },
      notifyAuthError: () => {
        /* noop */
      },
    };
  });
  await page.setViewportSize({ width: VIEWPORT.width, height: VIEWPORT.height });
}

test.describe.serial("v2.0 mobile pixel diff (WebView 5 屏)", () => {
  test.beforeAll(() => {
    [BASELINE_DIR, ACTUAL_DIR, DIFF_DIR].forEach((d) => {
      if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
    });
  });

  for (const screen of SCREENS) {
    test(`${screen.name} (${screen.description}) ≤ ${DIFF_THRESHOLD * 100}% diff`, async ({ page }) => {
      await setupMobileWebView(page);

      // 1. 加载 React 移动屏 + 截图
      await page.goto(screen.appPath);
      // networkidle 在 dev server HMR 下也能稳定 fire（无后台 polling）
      await page.waitForLoadState("networkidle").catch(() => {
        /* 容忍 timeout — 某些屏可能有长轮询 */
      });
      await page.waitForTimeout(500); // wait for css transitions / icons

      const actualPath = path.join(ACTUAL_DIR, `${screen.name}.png`);
      await page.screenshot({ path: actualPath, fullPage: false });

      // 2. baseline 检查
      const baselinePath = path.join(BASELINE_DIR, `${screen.name}.png`);
      if (!fs.existsSync(baselinePath)) {
        console.warn(
          `[${screen.name}] baseline 不存在，跳过 diff。请运行 npm run visual:baseline 生成。`,
        );
        test.skip();
        return;
      }

      // 3. pixelmatch
      const baselineBuf = fs.readFileSync(baselinePath);
      const actualBuf = fs.readFileSync(actualPath);
      // 尺寸不一致直接 fail（说明 baseline 跟实际渲染窗口不一样）
      const baseline = PNG.sync.read(baselineBuf);
      const actual = PNG.sync.read(actualBuf);
      expect(actual.width, "actual width must equal baseline width").toBe(baseline.width);
      expect(actual.height, "actual height must equal baseline height").toBe(baseline.height);

      const diff = new PNG({ width: baseline.width, height: baseline.height });
      const diffPixels = pixelmatch(
        baseline.data,
        actual.data,
        diff.data,
        baseline.width,
        baseline.height,
        { threshold: 0.1 }, // per-pixel 颜色阈值（0=严格, 1=宽松）
      );
      const diffPath = path.join(DIFF_DIR, `${screen.name}.diff.png`);
      fs.writeFileSync(diffPath, PNG.sync.write(diff));

      const totalPixels = baseline.width * baseline.height;
      const diffRatio = diffPixels / totalPixels;
      // eslint-disable-next-line no-console
      console.log(
        `[${screen.name}] diff = ${(diffRatio * 100).toFixed(2)}% (${diffPixels}/${totalPixels} px) → ${diffPath}`,
      );
      expect(
        diffRatio,
        `${screen.description} 像素差异 ${(diffRatio * 100).toFixed(2)}% 超过阈值 ${DIFF_THRESHOLD * 100}%；查看 ${diffPath}`,
      ).toBeLessThanOrEqual(DIFF_THRESHOLD);
    });
  }
});
