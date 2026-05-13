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
}

test.describe("v2.1 device capability banner", () => {
  test("home 顶部显示绿色 banner (realtime)", async ({ page }) => {
    await injectCapability(page, "realtime", "Xiaomi Mi 9 (Android 9)");
    await page.goto("/app/home");
    await page.waitForLoadState("networkidle").catch(() => {
      /* tolerate idle timeout */
    });

    const banner = page.locator(".cap-banner").first();
    await expect(banner).toBeVisible({ timeout: 5_000 });
    await expect(banner).toContainText("实时通话分析已就绪");
    await expect(banner).toContainText("Xiaomi Mi 9");
  });

  test("home 顶部显示橙色 banner (post_upload) + 详情链接", async ({ page }) => {
    await injectCapability(page, "post_upload", "Xiaomi MIUI 13 (Android 13)");
    await page.goto("/app/home");
    await page.waitForLoadState("networkidle").catch(() => {
      /* noop */
    });

    const banner = page.locator(".cap-banner.cap-banner-orange").first();
    await expect(banner).toBeVisible({ timeout: 5_000 });
    await expect(banner).toContainText("事后上传模式");
    await expect(banner.locator(".cap-banner-link")).toBeVisible();
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

    await expect(page.locator(".profile-section-card").first()).toContainText("录音能力", {
      timeout: 5_000,
    });
    await expect(page.locator(".cap-status-orange").first()).toContainText("事后上传");
    await expect(page.locator(".cap-rom").first()).toContainText("Xiaomi MIUI 13");
  });
});
