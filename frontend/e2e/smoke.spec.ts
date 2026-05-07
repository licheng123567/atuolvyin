import { test, expect, Page } from "@playwright/test";

const PASSWORD = "Demo@123!";

interface Role {
  name: string;
  phone: string;
  expectedText?: string;
}

const ROLES: Role[] = [
  { name: "platform_superadmin", phone: "13000000000", expectedText: "平台超管" },
  { name: "platform_ops", phone: "13000000001", expectedText: "运营员" },
  { name: "admin", phone: "13000000002", expectedText: "物业管理员" },
  { name: "supervisor", phone: "13000000003", expectedText: "督导小李" },
  { name: "agent_internal", phone: "13000000004", expectedText: "内勤小张" },
  { name: "agent_external", phone: "13000000005", expectedText: "外勤小王" },
  { name: "legal", phone: "13000000006", expectedText: "法务老周" },
  { name: "workorder", phone: "13000000007", expectedText: "工单小赵" },
  { name: "project_manager_property", phone: "13000000008", expectedText: "项目经理" },
  { name: "project_manager_provider", phone: "13000000009", expectedText: "项目经理" },
  { name: "provider_admin", phone: "13000000010", expectedText: "服务商管理员" },
];

/**
 * AppIntroModal (Sprint 14.3) auto-opens once after login on every PC session
 * unless `preferences.app_intro_dismissed=true`. Dismiss it before tests
 * navigate further; modal renders ~immediately after AppLayout mounts.
 */
async function dismissAppIntroIfPresent(page: Page) {
  const closeBtn = page.getByRole("button", { name: "知道了" });
  // 等 modal 真出现（preferences API + AppLayout mount）；2s 超时表示没出
  try {
    await closeBtn.waitFor({ state: "visible", timeout: 2500 });
    await closeBtn.click();
    await closeBtn.waitFor({ state: "hidden", timeout: 2000 });
  } catch {
    // 不存在，跳过
  }
}

async function login(page: Page, phone: string, password = PASSWORD) {
  await page.goto("/login");
  await page.fill('input[id="phone"]', phone);
  await page.fill('input[id="password"]', password);
  await Promise.all([
    page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 10_000 }),
    page.click('button[type="submit"]'),
  ]);
  await dismissAppIntroIfPresent(page);
}

test.describe("Login page — visual baseline", () => {
  test("login 页应显示双面板（左品牌 / 右表单）", async ({ page }) => {
    await page.goto("/login");
    // 品牌字"有证慧催"被 gradient span 拆成两段；多处出现（footer 等），用 first()
    await expect(page.getByText(/有证慧催/).first()).toBeVisible();
    await expect(page.getByText("欢迎回来")).toBeVisible();
    await expect(page.locator('input[id="phone"]')).toBeVisible();
    await expect(page.locator('input[id="password"]')).toBeVisible();
  });

  test("错误密码应报红 + 不跳转", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[id="phone"]', "13000000002");
    await page.fill('input[id="password"]', "wrong-password");
    await page.click('button[type="submit"]');
    await expect(page.getByText(/手机号或密码错误|登录失败/)).toBeVisible({ timeout: 5_000 });
    expect(page.url()).toContain("/login");
  });
});

test.describe("11 角色登录 + 主页加载", () => {
  for (const role of ROLES) {
    test(`${role.name} (${role.phone}) 登录后应加载到主区`, async ({ page }) => {
      await login(page, role.phone);
      expect(page.url()).not.toContain("/login");
      if (role.expectedText) {
        await expect(page.getByText(role.expectedText).first()).toBeVisible({ timeout: 5_000 });
      }
    });
  }
});

test.describe("admin 关键页", () => {
  test("admin 案件看板应渲染 6 列（待联系/跟进中/...）", async ({ page }) => {
    page.on("response", (r) => {
      if (r.status() === 401 || r.status() === 403) {
        console.log(`AUTH FAIL ${r.status()} ${r.url()}`);
      }
    });
    await login(page, "13000000002");
    const tok = await page.evaluate(() => localStorage.getItem("autoluyin_token"));
    console.log("token after login:", tok ? tok.slice(0, 30) + "..." : "NONE");
    await dismissAppIntroIfPresent(page);
    await page.goto("/admin/cases/kanban");
    await dismissAppIntroIfPresent(page);
    await page.waitForLoadState("networkidle");
    await page.getByText("加载中…").waitFor({ state: "hidden", timeout: 10_000 }).catch(() => undefined);
    for (const label of ["待联系", "跟进中", "承诺缴费", "已缴费", "升级中", "已关闭"]) {
      await expect(page.getByText(label).first()).toBeVisible({ timeout: 5_000 });
    }
  });

  test("admin 案件列表应能加载", async ({ page }) => {
    await login(page, "13000000002");
    await page.goto("/admin/cases");
    await dismissAppIntroIfPresent(page);
    await expect(page.getByRole("heading", { name: /案件/ })).toBeVisible({ timeout: 5_000 });
  });

  test("admin 系统配置页应同时显示 settings + AI 推送配置", async ({ page }) => {
    await login(page, "13000000002");
    await page.goto("/admin/settings");
    await dismissAppIntroIfPresent(page);
    await expect(page.getByText("系统配置").first()).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/AI 话术推送/)).toBeVisible({ timeout: 5_000 });
  });
});

test.describe("公开页（无登录）", () => {
  test("verify 页应可访问（无需登录）", async ({ page }) => {
    await page.goto("/verify");
    // 公开页应有基本可见内容（标题 / 输入框）
    await expect(page.locator("h1, h2, input").first()).toBeVisible({ timeout: 5_000 });
  });

  test("help/app 页应可访问（无需登录）", async ({ page }) => {
    await page.goto("/help/app");
    await expect(page.locator("h1, h2, [class*=container]").first()).toBeVisible({ timeout: 5_000 });
  });
});
