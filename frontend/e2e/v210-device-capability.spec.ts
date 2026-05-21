// v2.1 Task 8 — 设备录音能力感知 e2e
//
// 目的：验证 WebView 端 home/profile capability banner + cases/[id] 拨号
//       前 confirm。完全 mock 模式（page.addInitScript 注入 AndroidBridge
//       stub + page.route 拦截后端），不依赖真实 Android 真机。
//
// 跑法：`npx playwright test e2e/v210-device-capability.spec.ts --project=chromium`
//
// 范围：
//   - home  绿 / 橙 / 红 三档 banner
//   - cases/[id] incompatible 设备拨号 confirm
//   - profile 录音能力 section 三档展示
//
// 不覆盖（属其他测试套）：
//   - /admin/agent-devices 桌面列表（PC 端、走真实 backend）
//   - supervisor live-wall cap-badge（同上）
//   - Android 真机 RecordingScanner runtime 降级（Compose 层，需 adb 手测）
import { test, expect, type Page } from "@playwright/test";

const MOBILE_VIEWPORT = { width: 390, height: 844 } as const;

type Capability = "realtime" | "post_upload" | "incompatible";

/**
 * 在页面任意脚本之前注入：
 *  - fake JWT 让 MobileAuthGuard 通过
 *  - AndroidBridge stub：核心方法是 getCapability() 返回 JSON 字符串，
 *    WebView 端的 useCapability hook 同步解析渲染 banner
 */
async function injectCapability(
  page: Page,
  capability: Capability,
  rom = "Xiaomi MIUI 10",
): Promise<void> {
  await page.addInitScript(
    ([cap, romName]) => {
      window.localStorage.setItem("autoluyin_token", "fake-jwt-test");
      (window as unknown as { AndroidBridge: Record<string, unknown> }).AndroidBridge = {
        getJwt: () => "fake-jwt-test",
        getBackendUrl: () => "http://localhost:18000",
        getCapability: () =>
          JSON.stringify({
            capability: cap,
            guidance: `测试 guidance for ${cap}`,
            rom: romName,
            checkedAtMs: Date.now(),
          }),
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
    },
    [capability, rom] as const,
  );
  await page.setViewportSize(MOBILE_VIEWPORT);

  // v0.5.4 修正:v2.2 Module B 给 home/profile 加了 4 个 useCustom/useList API 调用,
  //   fake JWT 会让后端返 401 → Refine onError 自动登出跳 /login → 测试断言全错。
  //   统一拦截 /api/v1/** 返 200 空 paginated payload,保证页面停留在 /app/home。
  // 后端 PaginatedResponse 形状 {items, total, page, page_size};simpleRest custom 直返 body。
  await page.route(/\/api\/v1\//, async (route) => {
    const url = route.request().url();
    let body: unknown = { items: [], total: 0, page: 1, page_size: 10 };
    if (url.includes("today-kpi")) {
      body = {
        calls_target: 50,
        calls_today: 0,
        connected_today: 0,
        promised_today: 0,
        paid_today: 0,
        minutes_used_today: 0,
      };
    } else if (url.includes("performance")) {
      body = {
        user_id: 1,
        name: "测试",
        year_month: "2026-05",
        month_calls: 0,
        month_connected: 0,
        month_promised_cases: 0,
        month_paid_cases: 0,
        month_paid_amount: "0",
        conversion_rate: 0,
        minutes_used: 0,
        minutes_quota: 1000,
        rank_in_tenant: 1,
      };
    } else if (url.match(/\/agent\/cases\/\d+/)) {
      body = {
        id: 1,
        owner: { id: 1, name: "测试业主", phone: "13800138000", phone_masked: "138****8000" },
        amount_owed: "1000",
        months_overdue: 1,
        stage: "new",
        calls: [],
        timeline_events: [],
      };
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

test.describe("v2.1 device capability banner", () => {
  // v0.5.4 修正:v2.2 Module B1 把 realtime / post_upload 常驻 banner 收成右上角小圆点 +
  //   BottomSheet;只有 incompatible 仍保留红色 banner(合规强提示)。
  //   post_upload 另会显示「录音模式降级 banner」(.recording-downgrade-banner)。
  test("home 顶部显示绿色能力指示点 (realtime)", async ({ page }) => {
    await injectCapability(page, "realtime", "Xiaomi Mi 9 (Android 9)");
    await page.goto("/app/home");
    await page.waitForLoadState("networkidle").catch(() => {
      /* tolerate idle timeout */
    });

    // v2.2:realtime 收成 button[aria-label] 圆点(源码用全角冒号 U+FF1A)
    const indicator = page.getByRole("button", { name: /录音能力：实时通话分析已就绪/ }).first();
    await expect(indicator).toBeVisible({ timeout: 5_000 });
  });

  test("home 顶部显示橙色降级 banner (post_upload) + 详情链接", async ({ page }) => {
    await injectCapability(page, "post_upload", "Xiaomi MIUI 13 (Android 13)");
    await page.goto("/app/home");
    await page.waitForLoadState("networkidle").catch(() => {
      /* noop */
    });

    // v2.2 Module E1:post_upload 单独的「录音模式降级 banner」
    const banner = page.locator(".recording-downgrade-banner").first();
    await expect(banner).toBeVisible({ timeout: 5_000 });
    await expect(banner).toContainText("事后上传模式");
    // 同时右上角应有橙色指示点(源码全角冒号 U+FF1A)
    const indicator = page.getByRole("button", { name: /录音能力：事后上传模式/ }).first();
    await expect(indicator).toBeVisible();
  });

  test("home 顶部显示红色 banner (incompatible)", async ({ page }) => {
    await injectCapability(page, "incompatible", "Google Pixel 8 (Android 14)");
    await page.goto("/app/home");
    await page.waitForLoadState("networkidle").catch(() => {
      /* noop */
    });

    const banner = page.locator(".cap-banner.cap-banner-red").first();
    await expect(banner).toBeVisible({ timeout: 5_000 });
    await expect(banner).toContainText("录音不可用");
  });

  test("incompatible 设备拨号弹 confirm", async ({ page }) => {
    await injectCapability(page, "incompatible", "Pixel 8");

    // 拦截 case detail 接口，避免依赖真实 backend
    await page.route("**/api/v1/agent/cases/1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          owner: {
            id: 1,
            name: "测试业主",
            phone: "13800138000",
            phone_masked: "138****8000",
          },
          amount_owed: "1000",
          months_overdue: 1,
          stage: "new",
          calls: [],
          timeline_events: [],
        }),
      });
    });

    // 监听 confirm dialog，必须在 click 之前 attach
    let confirmDialogShown = false;
    page.on("dialog", async (dialog) => {
      expect(dialog.type()).toBe("confirm");
      expect(dialog.message()).toContain("无法保存通话录音");
      confirmDialogShown = true;
      await dialog.dismiss();
    });

    await page.goto("/app/cases/1");
    await page.waitForLoadState("networkidle").catch(() => {
      /* noop */
    });

    const dialBtn = page.getByRole("button", { name: /发起外呼/ });
    await dialBtn.click();
    expect(confirmDialogShown).toBe(true);
  });

  test("profile 录音能力 section 显示三档信息", async ({ page }) => {
    await injectCapability(page, "post_upload", "Xiaomi MIUI 13");
    await page.goto("/app/profile");
    await page.waitForLoadState("networkidle").catch(() => {
      /* noop */
    });

    // v0.5.4 修正:v2.2 重做 profile 录音 section,标题改为「录音设置」,
    //   不再有 .cap-status-orange / .cap-rom,改为 .recording-mode-row.active 标记当前模式 +
    //   .recording-rom 展示 ROM
    await expect(page.locator(".profile-section-card").first()).toContainText("录音设置", {
      timeout: 5_000,
    });
    const activeMode = page.locator(".recording-mode-row.active").first();
    // v2.3.1 起源码 MODES.label 用「通话后上传」(非「事后上传」)
    await expect(activeMode).toContainText("通话后上传");
    await expect(page.locator(".recording-rom").first()).toContainText("Xiaomi MIUI 13");
  });
});
