// v2.0 Task 9 — Android App UI 1:1 重写：baseline 截图生成
//
// 目的：渲染 ui/app-agent.html 内嵌的 .phone-screen mockup（5 个 WebView 屏的 section），
//       截图作为 v200-mobile-pixel-diff.spec.ts 的对照基线。
//
// 跑法：`npm run visual:baseline`
// 产物：frontend/tests/visual-baselines/v2.0-mobile/{s1-home,s5-cases,s6-case-detail,s7-call-history,s8-profile}.png
//       这些 PNG 必须 commit 进 git。
//
// 注意：
//   - app-agent.html 里 .phone-screen 是 fixed 尺寸（375×812 设计稿原样，
//     但里面 .screen-content 滚动）。截 .phone-screen 元素而不是 viewport，
//     拿到的尺寸由 HTML/CSS 决定，不等于 viewport 390×844；
//     pixel diff 测试在 setupMobileWebView 中用 viewport 390×844 截全屏 + 也对比 pingjs PNG dimension，
//     所以这两个尺寸需要保持一致。
//   - 解决方式：baseline 也截 viewport（fullPage: false）大小，
//     先把 .phone-screen 在 page 里 stretch 到 viewport 尺寸再截。
//   - app-agent.html 用 .page-section.active 控制可见性，需要先把目标 section 切成 active。
import { test } from "@playwright/test";
import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const VIEWPORT = { width: 390, height: 844 } as const;
const BASELINE_DIR = path.join(__dirname, "../tests/visual-baselines/v2.0-mobile");
// app-agent.html 在仓库根的 ui/ 下；__dirname 是 frontend/e2e/
const DESIGN_HTML_PATH = path.resolve(__dirname, "../../ui/app-agent.html");

interface BaselineSpec {
  name: string;
  selector: string; // section id in app-agent.html
}

const SCREENS: BaselineSpec[] = [
  { name: "s1-home", selector: "#app-home" },
  { name: "s5-cases", selector: "#app-cases" },
  { name: "s6-case-detail", selector: "#app-case-detail" },
  { name: "s7-call-history", selector: "#app-call-history" },
  { name: "s8-profile", selector: "#app-profile" },
];

test.describe("v2.0 baseline generation (manual run only)", () => {
  test.beforeAll(() => {
    if (!fs.existsSync(BASELINE_DIR)) fs.mkdirSync(BASELINE_DIR, { recursive: true });
    if (!fs.existsSync(DESIGN_HTML_PATH)) {
      throw new Error(`app-agent.html not found at ${DESIGN_HTML_PATH}`);
    }
  });

  for (const screen of SCREENS) {
    test(`gen baseline ${screen.name}`, async ({ page }) => {
      await page.setViewportSize({ width: VIEWPORT.width, height: VIEWPORT.height });
      // file:// 加载本地 HTML（design-system.css 用相对路径 assets/design-system.css，能命中）
      await page.goto(`file://${DESIGN_HTML_PATH}`);
      await page.waitForLoadState("domcontentloaded");

      // 切换可见 section（app-agent.html 默认 #app-home active）
      await page.evaluate((selector: string) => {
        document
          .querySelectorAll(".screen-content .page-section")
          .forEach((el) => el.classList.remove("active"));
        const target = document.querySelector(selector);
        target?.classList.add("active");
        // 同步底部 tab 高亮（仅视觉一致性，diff 时也对得上）
        document.querySelectorAll(".tab-item").forEach((el) => el.classList.remove("active"));
        const tabId = selector.replace(/^#/, "");
        const tab = document.querySelector(`.tab-item[data-tab="${tabId}"]`);
        tab?.classList.add("active");
      }, screen.selector);

      // 把 .phone-frame 撑到 viewport 尺寸；让 baseline 跟 pixel-diff 截全屏的尺寸一致。
      // .phone-screen 在 .phone-frame 内（参考 app-agent.html 行 906-907）；
      // 隐藏 body 下其它兄弟（.screen-nav 顶栏 等），保留 .phone-frame，去掉外壳样式。
      await page.addStyleTag({
        content: `
          html, body { margin: 0 !important; padding: 0 !important; background: #fff; }
          /* 隐藏页面里其它 demo 框架（top nav 选项条等），只留 .phone-frame */
          body > *:not(.phone-frame):not(script):not(style) { display: none !important; }
          .phone-frame {
            position: fixed !important;
            top: 0 !important; left: 0 !important;
            width: ${VIEWPORT.width}px !important;
            height: ${VIEWPORT.height}px !important;
            min-height: ${VIEWPORT.height}px !important;
            border: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
          }
          .phone-screen {
            min-height: ${VIEWPORT.height}px !important;
            height: ${VIEWPORT.height}px !important;
          }
        `,
      });
      await page.waitForTimeout(800); // wait for fonts + svg / icon font load

      const baselinePath = path.join(BASELINE_DIR, `${screen.name}.png`);
      await page.screenshot({ path: baselinePath, fullPage: false });
      // eslint-disable-next-line no-console
      console.log(`baseline saved: ${baselinePath}`);
    });
  }
});
