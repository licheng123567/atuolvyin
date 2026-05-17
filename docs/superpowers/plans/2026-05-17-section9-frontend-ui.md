# §9 配套前端 UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为已上线的 §9 后端能力（§9.1 服务商法务、§9.2 减免归属+佣金）补齐配套 PC 前端 UI。

**Architecture:** 前端 `frontend/`（TypeScript + React + Refine.dev v5）新增 §9.1 服务商法务 4 个页面 + §9.2 内勤提成 2 个页面，并增改减免/佣金/项目费率相关现有页面；另含 3 处配套小后端改动。沿用现有代码模式，不引入新库、不改视觉风格。

**Tech Stack:** TypeScript + React + Refine.dev v5 + Tailwind + lucide-react；后端 FastAPI；测试 Vitest + React Testing Library + Playwright（前端）、pytest + testcontainers（后端）。

**来源 spec:** `docs/superpowers/specs/2026-05-17-section9-frontend-ui-design.md`
**分支:** `feat/section9-frontend-ui`（已创建，当前分支）

---

## 关键约定（每个 task 都适用）

### 代码风格 —— 跟随真实代码库
- 项目**并未使用 shadcn/ui 原生组件**（尽管 DESIGN_SPEC 提及）。实际用的是自定义 CSS class：`.ds-card` / `.card-body`、`.ds-btn` `.ds-btn-primary` `.ds-btn-secondary` `.ds-btn-ghost` `.ds-btn-sm`、`.ds-badge` `.ds-badge-blue`、`.form-group` `.form-label` `.form-control` `.req`、`.page-header` `.page-title` `.page-subtitle`、`.table-wrap` + 手写 `<table>`、`.modal-overlay` `.ds-modal` `.modal-header` `.modal-title` `.modal-close` `.modal-body` `.modal-footer`、`.two-col`。图标用 `lucide-react`。**新页面一律沿用这些 class**，禁止引入 shadcn 组件、禁止 `any` 类型。
- CSS 变量：`var(--color-primary)`、`var(--color-neutral-50/500)`、`var(--radius-md)`。

### 数据层（Refine）
- 自定义（非 resource）接口用 `useCustom` / `useCustomMutation` / `useInvalidate`（`@refinedev/core`）。`url` 写**相对路径**，dataProvider 自动拼 `/api/v1/`。`useCustom` 返回 `{ query }`，数据在 `query.data?.data`。查询参数走 `config: { query }`。
- 范本文件：`frontend/src/pages/discount/api.ts`（hooks 范式）、`frontend/src/pages/provider/commission/index.tsx`（useCustom + 页面）。
- 后端分页响应 `{ items, total, page, page_size }`。Decimal 字段在 JSON 里是 **string**。

### 文件上传
- 走原生 `FormData` + `fetch`（不经 Refine），范本 `frontend/src/pages/legal/cases/[id].tsx` 的 `LegalDocumentsPanel`：
  ```ts
  const apiBase = import.meta.env.VITE_API_BASE ?? "";
  const fd = new FormData(); fd.append("file", file);
  const resp = await fetch(`${apiBase}/api/v1/<path>`, {
    method: "POST",
    headers: { Authorization: `Bearer ${localStorage.getItem("autoluyin_token") ?? ""}` },
    body: fd,
  });
  ```

### 路由与导航
- 路由在 `frontend/src/App.tsx` 的 `<Routes>` 受保护区块内，直接 `import` 页面组件 + `<Route path=... element={<X/>} />`（无 lazy）。
- 导航在 `frontend/src/config/nav.ts`，`getNavSections(role, scope)` 按 scope 返回。

### 测试
- 前端组件测试：Vitest + React Testing Library，文件放 `__tests__/` 子目录，命名 `*.test.tsx`。范本 `frontend/src/components/realtime/__tests__/RealtimeCallShell.test.tsx`。
- 页面测试用 `vi.mock("../api", ...)` mock 掉本页 `api.ts` 的 hooks，再 `render(<MemoryRouter>…</MemoryRouter>)` 断言。详情页用 `<MemoryRouter initialEntries={["/x/1"]}><Routes><Route path="/x/:id" …/></Routes></MemoryRouter>` 提供路由参数。
- 跑前端测试：`cd frontend && npx vitest run <文件>`。前端 lint：`cd frontend && npm run lint`。typecheck：`cd frontend && npx tsc -p tsconfig.json --noEmit`。
- 后端：`cd poc/backend && python3.12 -m pytest <文件> -v`；lint `python3.12 -m ruff check <文件>`。
- 后端自定义 HTTPException handler 返回**扁平** body `{code,message}`。

### Git
- `git add` 从仓库根 `/Users/shuo/AI/autoluyin` 执行。Conventional Commits，前缀 `feat(§9-fe):` / `feat(§9-be):` / `test(§9-fe):`。

---

## File Structure

**新建（前端）：**
```
frontend/src/pages/provider/legal/
├── api.ts                         — Refine hooks + DTO 类型
├── cases/index.tsx                — 法务案件浏览列表
├── cases/[id].tsx                 — 案件详情 + 发起转化请求
├── requests/index.tsx             — 转化请求列表
├── requests/[id].tsx              — 请求详情 + 补充材料
└── __tests__/*.test.tsx           — 4 个页面测试

frontend/src/pages/admin/agent-commissions/
├── api.ts                         — Refine hooks + DTO 类型
├── index.tsx                      — 内勤提成列表
├── [id].tsx                       — 单人逐案明细
└── __tests__/*.test.tsx           — 2 个页面测试
```

**修改：** `frontend/src/config/nav.ts`、`frontend/src/App.tsx`、`frontend/src/pages/discount/{api.ts,ApprovalListPage.tsx,ApprovalDetailPage.tsx}`、`frontend/src/pages/provider/commission/index.tsx`、`frontend/src/pages/admin/projects/{new.tsx,edit.tsx}`、`frontend/src/pages/provider/projects/index.tsx`、`frontend/e2e/per-role-pages.spec.ts`；后端 `poc/backend/app/schemas/discount.py`、`poc/backend/app/api/discount_offers.py`、`poc/backend/app/api/admin.py`。

---

# Part 1 — 配套后端改动（前端依赖其契约，先做）

## Task 1: 后端 — DiscountOfferOut 加 provider_name

**Files:**
- Modify: `poc/backend/app/schemas/discount.py`（`DiscountOfferOut`）
- Modify: `poc/backend/app/api/discount_offers.py`（`_to_out`，约 line 109-122）
- Test: `poc/backend/tests/api/test_discount_offers_attribution.py`（已存在，追加）

- [ ] **Step 1: 写失败测试** — 在 `test_discount_offers_attribution.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_provider_agent_offer_carries_provider_name(
    client, db_session, seeded_tenant, seeded_case
):
    provider = _provider(db_session)
    headers = _provider_agent_headers(db_session, seeded_tenant.id, provider.id)
    resp = await client.post(
        f"/api/v1/cases/{seeded_case.id}/discount-offers", json=_BODY, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["provider_name"] == provider.name
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_discount_offers_attribution.py::test_provider_agent_offer_carries_provider_name -v`
Expected: FAIL — 响应无 `provider_name` 键。

- [ ] **Step 3: schema 加字段** — `app/schemas/discount.py` 的 `DiscountOfferOut` 里，`provider_id` 字段之后加：

```python
    provider_name: str | None = None
```

- [ ] **Step 4: `_to_out` enrich** — `app/api/discount_offers.py` 顶部 import 加 `from app.models.tenant import ServiceProvider`（若已 import 其他 tenant 模型则合并）。`_to_out` 函数内，构造 `out` 之后、`return` 之前加：

```python
    provider = db.get(ServiceProvider, offer.provider_id) if offer.provider_id else None
    out.provider_name = provider.name if provider else None
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_discount_offers_attribution.py -v`
Expected: PASS（全部 3 个）。

- [ ] **Step 6: lint + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/schemas/discount.py app/api/discount_offers.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/discount.py poc/backend/app/api/discount_offers.py poc/backend/tests/api/test_discount_offers_attribution.py
git commit -m "feat(§9-be): DiscountOfferOut 透出 provider_name 服务商来源"
```

---

## Task 2: 后端 — get_agent_commission_detail 迁 §9.2 算法

**Files:**
- Modify: `poc/backend/app/api/admin.py`（`AgentCommissionLineItem` 约 line 582-586；`get_agent_commission_detail` 约 line 713-773）
- Test: `poc/backend/tests/api/test_admin_agent_commissions.py`（已存在，追加）

**背景:** `list_agent_commissions`（同文件，§9.2 已重写）是参照范本 —— 逐案「实收（扣已执行减免）× 项目内勤率」。`get_agent_commission_detail` 当前仍是旧口径（`amount_owed × 固定 INTERNAL_AGENT_COMMISSION_RATE`），本 task 迁到同口径，并给行项加 `commission_rate`。

- [ ] **Step 1: 写失败测试** — 在 `test_admin_agent_commissions.py` 末尾追加（复用文件内已有 helper `_project` / `_paid_case` / `_executed_offer`）：

```python
@pytest.mark.asyncio
async def test_agent_commission_detail_per_case_rate_and_discount(
    client, db_session, seeded_tenant, seeded_owner, seeded_member_user, admin_auth_headers
):
    p = _project(db_session, seeded_tenant.id, "明细佣金项目", Decimal("0.0800"))
    c1 = _paid_case(
        db_session, seeded_tenant.id, seeded_owner.id, seeded_member_user.id, p.id, "1000.00"
    )
    _executed_offer(db_session, seeded_tenant.id, c1.id, "600.00")  # 实收 600

    resp = await client.get(
        f"/api/v1/admin/agent-commissions/{seeded_member_user.id}?year_month=2026-05",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert Decimal(str(body["base_amount"])) == Decimal("600.00")
    assert Decimal(str(body["commission"])) == Decimal("48.00")  # 600 × 0.08
    item = next(it for it in body["items"] if it["case_id"] == c1.id)
    assert Decimal(str(item["paid_amount"])) == Decimal("600.00")
    assert Decimal(str(item["commission_rate"])) == Decimal("0.0800")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_admin_agent_commissions.py::test_agent_commission_detail_per_case_rate_and_discount -v`
Expected: FAIL — 旧算法 base=1000、commission=50.00；且 item 无 `commission_rate` 键。

- [ ] **Step 3: `AgentCommissionLineItem` 加字段** — `app/api/admin.py` 的 `AgentCommissionLineItem` 类，在 `paid_at` 之后加：

```python
    commission_rate: Decimal  # §9.2 — 该案所属项目的内勤佣金率
```

- [ ] **Step 4: 改写 `get_agent_commission_detail`** — 把该函数从 `target = db.get(...)` 之后的函数体（构造 `period_start/period_end` 起、到 `return`）替换为下面这版（参照同文件 `list_agent_commissions`）：

```python
    from app.models.case import CollectionCase, OwnerProfile, Project
    from app.services.commission import executed_discount_amounts, internal_agent_rate

    period_start, period_end = _month_window(year_month)
    rows = db.execute(
        select(CollectionCase, OwnerProfile)
        .join(OwnerProfile, OwnerProfile.id == CollectionCase.owner_id)
        .where(
            CollectionCase.assigned_to == user_id,
            CollectionCase.tenant_id == tenant_id,
            CollectionCase.stage == "paid",
            CollectionCase.updated_at >= period_start,
            CollectionCase.updated_at < period_end,
        )
        .order_by(CollectionCase.updated_at.desc())
    ).all()

    executed = executed_discount_amounts(db, tenant_id, [c.id for c, _o in rows])
    project_cache: dict[int, Project | None] = {}

    def _project(project_id: int | None) -> Project | None:
        if project_id is None:
            return None
        if project_id not in project_cache:
            project_cache[project_id] = db.get(Project, project_id)
        return project_cache[project_id]

    items: list[AgentCommissionLineItem] = []
    base = D("0")
    commission = D("0")
    for c, o in rows:
        collected = executed[c.id] if c.id in executed else D(str(c.amount_owed or 0))
        rate = internal_agent_rate(_project(c.project_id))
        base += collected
        commission += (collected * rate).quantize(D("0.01"))
        items.append(
            AgentCommissionLineItem(
                case_id=c.id,
                owner_name=o.name,
                paid_amount=collected,
                paid_at=c.updated_at,
                commission_rate=rate,
            )
        )
    effective_rate = float(commission / base) if base > 0 else INTERNAL_AGENT_COMMISSION_RATE
    return AgentCommissionDetail(
        user_id=target.id,
        name=target.name,
        year_month=year_month,
        commission_rate=effective_rate,
        base_amount=base,
        commission=commission,
        items=items,
    )
```

> `D` 是函数内已有的 `from decimal import Decimal as D`。保留函数原签名、装饰器、`tenant_id` 校验、`target` 查找不动。

- [ ] **Step 5: 跑测试确认通过 + 回归**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_admin_agent_commissions.py -v`
Expected: PASS（全部）。

- [ ] **Step 6: lint + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/api/admin.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/admin.py poc/backend/tests/api/test_admin_agent_commissions.py
git commit -m "feat(§9-be): 内勤提成详情迁 §9.2 算法（逐案实收×项目率）"
```

---

# Part 2 — §9.1 服务商法务前端

## Task 3: provider/legal/api.ts — hooks + 类型

**Files:**
- Create: `frontend/src/pages/provider/legal/api.ts`

参照 `frontend/src/pages/discount/api.ts`。后端端点前缀 `provider/legal`（dataProvider 自动补 `/api/v1/`）。

- [ ] **Step 1: 创建 `frontend/src/pages/provider/legal/api.ts`**，完整内容：

```typescript
// §9.1 — 服务商法务前端 API hooks
import { useCustom, useCustomMutation, useInvalidate } from "@refinedev/core";

export interface ProviderLegalCaseListItem {
  case_id: number;
  owner_name: string | null;
  owner_phone_masked: string | null;
  building: string | null;
  room: string | null;
  project_id: number | null;
  project_name: string | null;
  amount_owed: string | null;
  months_overdue: number | null;
  stage: string;
}

export interface ProviderLegalCaseDetail extends ProviderLegalCaseListItem {
  pool_type: string;
  status: string;
  principal_amount: string | null;
  late_fee_amount: string | null;
  arrears_reason: string | null;
  last_contact_at: string | null;
  monthly_contact_count: number;
  priority_score: number;
  call_count: number;
  last_call_at: string | null;
}

export interface ProviderLegalRequestMaterial {
  id: number;
  request_id: number;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  uploaded_by: number;
  created_at: string;
}

export interface ProviderLegalRequest {
  id: number;
  tenant_id: number;
  case_id: number;
  owner_name: string | null;
  project_id: number | null;
  project_name: string | null;
  amount_owed: string | null;
  reason: string | null;
  status: string; // pending | approved | rejected | cancelled
  reviewer_note: string | null;
  reviewed_at: string | null;
  related_order_id: number | null;
  order_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProviderLegalRequestDetail extends ProviderLegalRequest {
  materials: ProviderLegalRequestMaterial[];
}

interface ListResp<T> {
  items: T[];
  total: number;
}

export function useProviderLegalCases(params: { page: number; pageSize: number }) {
  const { query } = useCustom<ListResp<ProviderLegalCaseListItem>>({
    url: "provider/legal/cases",
    method: "get",
    config: { query: { page: params.page, page_size: params.pageSize } },
  });
  return {
    items: query.data?.data?.items ?? [],
    total: query.data?.data?.total ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}

export function useProviderLegalCase(caseId: number | undefined) {
  const { query } = useCustom<ProviderLegalCaseDetail>({
    url: caseId ? `provider/legal/cases/${caseId}` : "provider/legal/cases/0",
    method: "get",
    queryOptions: { enabled: !!caseId },
  });
  return { detail: query.data?.data, isLoading: query.isLoading, isError: query.isError };
}

export function useProviderLegalRequests(params: { page: number; pageSize: number }) {
  const { query } = useCustom<ListResp<ProviderLegalRequest>>({
    url: "provider/legal/conversion-requests",
    method: "get",
    config: { query: { page: params.page, page_size: params.pageSize } },
  });
  return {
    items: query.data?.data?.items ?? [],
    total: query.data?.data?.total ?? 0,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}

export function useProviderLegalRequest(requestId: number | undefined) {
  const { query } = useCustom<ProviderLegalRequestDetail>({
    url: requestId
      ? `provider/legal/conversion-requests/${requestId}`
      : "provider/legal/conversion-requests/0",
    method: "get",
    queryOptions: { enabled: !!requestId },
  });
  return {
    detail: query.data?.data,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export function useCreateConversionRequest() {
  const { mutate, mutation } = useCustomMutation<ProviderLegalRequest>();
  const invalidate = useInvalidate();
  return {
    create: (
      caseId: number,
      reason: string,
      opts?: { onSuccess?: (r: ProviderLegalRequest) => void; onError?: (e: unknown) => void },
    ) =>
      mutate(
        {
          url: `provider/legal/cases/${caseId}/conversion-request`,
          method: "post",
          values: { reason },
        },
        {
          onSuccess: (resp) => {
            invalidate({ resource: "provider/legal/conversion-requests", invalidates: ["list"] });
            opts?.onSuccess?.(resp.data as unknown as ProviderLegalRequest);
          },
          onError: (e) => opts?.onError?.(e),
        },
      ),
    isPending: mutation.isPending,
  };
}

const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export async function uploadRequestMaterial(
  requestId: number,
  file: File,
): Promise<ProviderLegalRequestMaterial> {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await fetch(
    `${apiBase}/api/v1/provider/legal/conversion-requests/${requestId}/materials`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${localStorage.getItem("autoluyin_token") ?? ""}` },
      body: fd,
    },
  );
  if (!resp.ok) {
    const err = (await resp.json().catch(() => ({}))) as { message?: string };
    throw new Error(err.message ?? `上传失败 (HTTP ${resp.status})`);
  }
  return (await resp.json()) as ProviderLegalRequestMaterial;
}

export async function getMaterialDownloadUrl(
  requestId: number,
  materialId: number,
): Promise<string> {
  const resp = await fetch(
    `${apiBase}/api/v1/provider/legal/conversion-requests/${requestId}/materials/${materialId}`,
    { headers: { Authorization: `Bearer ${localStorage.getItem("autoluyin_token") ?? ""}` } },
  );
  if (!resp.ok) throw new Error(`获取下载链接失败 (HTTP ${resp.status})`);
  const data = (await resp.json()) as { download_url: string };
  return data.download_url;
}
```

- [ ] **Step 2: typecheck**

Run: `cd frontend && npx tsc -p tsconfig.json --noEmit`
Expected: 无该文件相关报错。

- [ ] **Step 3: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/provider/legal/api.ts
git commit -m "feat(§9-fe): 服务商法务前端 api.ts（hooks + 类型）"
```

---

## Task 4: 法务案件浏览列表页

**Files:**
- Create: `frontend/src/pages/provider/legal/cases/index.tsx`
- Test: `frontend/src/pages/provider/legal/__tests__/cases-list.test.tsx`

参照范本：`frontend/src/pages/discount/ApprovalListPage.tsx`（页面外壳 + 表格 + 客户端关键词过滤 + 分页）。后端 `GET provider/legal/cases` 仅支持 `page`/`page_size`，搜索为**客户端**过滤当前页（与 discount 页一致）。

- [ ] **Step 1: 写失败测试** — `frontend/src/pages/provider/legal/__tests__/cases-list.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api", () => ({
  useProviderLegalCases: () => ({
    items: [
      {
        case_id: 1, owner_name: "张三", owner_phone_masked: "138****8888",
        building: "1栋", room: "101", project_id: 9, project_name: "阳光花园",
        amount_owed: "3000.00", months_overdue: 3, stage: "跟进中",
      },
    ],
    total: 1, isLoading: false, isError: false,
  }),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { ProviderLegalCasesPage } from "../cases/index";

describe("ProviderLegalCasesPage", () => {
  it("renders case row with owner and project", () => {
    render(<MemoryRouter><ProviderLegalCasesPage /></MemoryRouter>);
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("阳光花园")).toBeDefined();
    expect(screen.getByText("138****8888")).toBeDefined();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/cases-list.test.tsx`
Expected: FAIL — 模块 `../cases/index` 不存在。

- [ ] **Step 3: 创建 `cases/index.tsx`** —— 导出 `ProviderLegalCasesPage`。要求：
  - `useState` 管 `page`（默认 1，`PAGE_SIZE = 20`）、`keyword`。
  - 调 `useProviderLegalCases({ page, pageSize: PAGE_SIZE })`。
  - 客户端按 `keyword`（业主名 / 房号）`useMemo` 过滤当前页 items。
  - 页面外壳：`<div className="page-header">` 内 `<h1 className="page-title">`（带 `<Scale>` 图标）「法务案件」+ `<p className="page-subtitle">`「浏览本服务商承接项目下的案件（只读，手机号脱敏）」。
  - 搜索框 `<input className="form-control">`（占位「搜索业主 / 房号」）。
  - `<div className="table-wrap"><table>`，列头：业主/房号、项目、欠费金额、逾期、案件阶段、操作。
  - 行：业主名 `<strong>` + 房号（`building`+`room`）+ 第二行小字 `owner_phone_masked`；项目 `project_name`；`¥{amount_owed}`；`{months_overdue} 月`；`stage`（`<span className="ds-badge ds-badge-blue">`）；操作列 `<button className="ds-btn ds-btn-ghost ds-btn-sm">` 点击 `go({ to: '/provider/legal/cases/' + case_id })`（`useGo` from `@refinedev/core`）。
  - 加载态：`isLoading` 时表格体显示「加载中…」单行；空：过滤后为空显示「暂无案件」/「无匹配结果」。
  - 分页：`total > PAGE_SIZE` 时底部「上一页 / {page} / 下一页」按钮（`.ds-btn ds-btn-secondary ds-btn-sm`），参照 `legal/cases/index.tsx` 分页写法。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/cases-list.test.tsx`
Expected: PASS。

- [ ] **Step 5: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/provider/legal/cases/index.tsx frontend/src/pages/provider/legal/__tests__/cases-list.test.tsx
git commit -m "feat(§9-fe): 服务商法务-案件浏览列表页"
```

---

## Task 5: 案件详情页 + 发起转化请求

**Files:**
- Create: `frontend/src/pages/provider/legal/cases/[id].tsx`
- Test: `frontend/src/pages/provider/legal/__tests__/case-detail.test.tsx`

参照 `frontend/src/pages/discount/ApprovalDetailPage.tsx`（详情卡 + `useParams`）。

> **设计简化（对 spec §4.2）:** `ProviderLegalCaseDetail` 后端 DTO **不含**「该案是否已有请求」字段，故案件详情页**不做**预判横幅/按钮置灰。「发起法务转化请求」按钮始终可点；若后端对重复发起有约束，以其错误响应 Toast 提示。spec §4.2 已允许「以后端错误响应为准」。

- [ ] **Step 1: 写失败测试** — `__tests__/case-detail.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../api", () => ({
  useProviderLegalCase: () => ({
    detail: {
      case_id: 1, owner_name: "张三", owner_phone_masked: "138****8888",
      building: "1栋", room: "101", project_name: "阳光花园", pool_type: "public",
      stage: "跟进中", status: "active", amount_owed: "3000.00", principal_amount: "2800.00",
      late_fee_amount: "200.00", months_overdue: 3, arrears_reason: null,
      last_contact_at: null, monthly_contact_count: 0, priority_score: 1000,
      call_count: 0, last_call_at: null,
    },
    isLoading: false, isError: false,
  }),
  useCreateConversionRequest: () => ({ create: vi.fn(), isPending: false }),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { ProviderLegalCaseDetailPage } from "../cases/[id]";

describe("ProviderLegalCaseDetailPage", () => {
  it("renders case info and the create-request button", () => {
    render(
      <MemoryRouter initialEntries={["/provider/legal/cases/1"]}>
        <Routes>
          <Route path="/provider/legal/cases/:id" element={<ProviderLegalCaseDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("发起法务转化请求")).toBeDefined();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/case-detail.test.tsx`
Expected: FAIL — 模块不存在。

- [ ] **Step 3: 创建 `cases/[id].tsx`** —— 导出 `ProviderLegalCaseDetailPage`。要求：
  - `useParams<{ id: string }>()` 取 `caseId = Number(id)`。`useProviderLegalCase(caseId)`。
  - `isLoading` → 「加载中…」；`isError || !detail` → 「案件不存在或无权限」。
  - 顶部：返回链接（`<button>` + `<ArrowLeft>` → `go({ to: '/provider/legal/cases' })`）；`<h1>`「案件详情 · {building}{room} {owner_name}」；右上 `<button className="ds-btn ds-btn-primary">`「发起法务转化请求」→ 打开 Dialog。
  - 案件信息卡（`.ds-card` > `.card-body`）：grid 三列，字段 —— 业主、手机号（`owner_phone_masked`）、项目、房号、欠费金额（`¥`）、本金/滞纳金、逾期月数、案件阶段、最近跟进（`last_contact_at`）、优先级分。
  - 发起请求 Dialog（`.modal-overlay` > `.ds-modal`，参照 `provider/projects/index.tsx` 的 `AssignPmModal`）：标题「发起法务转化请求」；一个 `<textarea className="form-control">` 填申请理由（必填，前端校验非空，`maxLength={2000}`）；底部「取消」+「提交」按钮。提交调 `useCreateConversionRequest().create(caseId, reason, { onSuccess: (r) => go({ to: '/provider/legal/requests/' + r.id }), onError: (e) => setErr(...) })`。`isPending` 时按钮 loading + 禁用。错误信息显示在 Dialog 内（`color: var(--color-danger)`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/case-detail.test.tsx`
Expected: PASS。

- [ ] **Step 5: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/provider/legal/cases/\[id\].tsx frontend/src/pages/provider/legal/__tests__/case-detail.test.tsx
git commit -m "feat(§9-fe): 服务商法务-案件详情页 + 发起转化请求"
```

---

## Task 6: 转化请求列表页

**Files:**
- Create: `frontend/src/pages/provider/legal/requests/index.tsx`
- Test: `frontend/src/pages/provider/legal/__tests__/requests-list.test.tsx`

参照 Task 4 的列表页结构。

- [ ] **Step 1: 写失败测试** — `__tests__/requests-list.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api", () => ({
  useProviderLegalRequests: () => ({
    items: [
      {
        id: 7, tenant_id: 1, case_id: 1, owner_name: "张三", project_id: 9,
        project_name: "阳光花园", amount_owed: "3000.00", reason: "逾期3月沟通无果",
        status: "pending", reviewer_note: null, reviewed_at: null,
        related_order_id: null, order_status: null,
        created_at: "2026-05-10T14:22:00", updated_at: "2026-05-10T14:22:00",
      },
    ],
    total: 1, isLoading: false, isError: false,
  }),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { ProviderLegalRequestsPage } from "../requests/index";

describe("ProviderLegalRequestsPage", () => {
  it("renders request row with status badge", () => {
    render(<MemoryRouter><ProviderLegalRequestsPage /></MemoryRouter>);
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("待审批")).toBeDefined();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/requests-list.test.tsx`
Expected: FAIL — 模块不存在。

- [ ] **Step 3: 创建 `requests/index.tsx`** —— 导出 `ProviderLegalRequestsPage`。要求：
  - `useState` 管 `page`（`PAGE_SIZE = 20`）。`useProviderLegalRequests({ page, pageSize })`。
  - 页头：`<h1 className="page-title">`（`<ClipboardList>` 图标）「法务转化请求」+ 副标题「本服务商法务发起的转化请求 · 跟踪审批结果与订单进度」。
  - 表格列：案件（`owner_name`）、项目、申请理由（截断展示）、审批状态、订单状态、提交时间（`created_at` 截 10 位）、操作。
  - 审批状态 Badge —— 用一个映射常量：`pending`→`<span className="ds-badge" style={{background:'#FEF3C7',color:'#D97706'}}>待审批</span>`、`approved`→绿（`#DCFCE7`/`#057A55`「已通过」）、`rejected`→红（`#FEE2E2`/`#E02424`「已驳回」）、`cancelled`→灰（`#F3F4F6`/`#4B5563`「已取消」）。
  - 订单状态：`order_status` 为空显示「—」，否则 `<span className="ds-badge ds-badge-blue">{order_status}</span>`。
  - 操作列「查看」→ `go({ to: '/provider/legal/requests/' + id })`。
  - 加载 / 空 / 分页同 Task 4。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/requests-list.test.tsx`
Expected: PASS。

- [ ] **Step 5: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/provider/legal/requests/index.tsx frontend/src/pages/provider/legal/__tests__/requests-list.test.tsx
git commit -m "feat(§9-fe): 服务商法务-转化请求列表页"
```

---

## Task 7: 转化请求详情页 + 补充材料

**Files:**
- Create: `frontend/src/pages/provider/legal/requests/[id].tsx`
- Test: `frontend/src/pages/provider/legal/__tests__/request-detail.test.tsx`

参照 `frontend/src/pages/legal/cases/[id].tsx` 的 `LegalDocumentsPanel`（文件上传面板）。

- [ ] **Step 1: 写失败测试** — `__tests__/request-detail.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../api", () => ({
  useProviderLegalRequest: () => ({
    detail: {
      id: 7, tenant_id: 1, case_id: 1, owner_name: "张三", project_id: 9,
      project_name: "阳光花园", amount_owed: "3000.00", reason: "逾期3月沟通无果",
      status: "pending", reviewer_note: null, reviewed_at: null,
      related_order_id: null, order_status: null,
      created_at: "2026-05-10T14:22:00", updated_at: "2026-05-10T14:22:00",
      materials: [
        { id: 3, request_id: 7, filename: "证据.pdf", content_type: "application/pdf",
          size_bytes: 1234, uploaded_by: 5, created_at: "2026-05-10T14:25:00" },
      ],
    },
    isLoading: false, isError: false, refetch: vi.fn(),
  }),
  uploadRequestMaterial: vi.fn(),
  getMaterialDownloadUrl: vi.fn(),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { ProviderLegalRequestDetailPage } from "../requests/[id]";

describe("ProviderLegalRequestDetailPage", () => {
  it("renders request info and material list", () => {
    render(
      <MemoryRouter initialEntries={["/provider/legal/requests/7"]}>
        <Routes>
          <Route path="/provider/legal/requests/:id" element={<ProviderLegalRequestDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(/逾期3月沟通无果/)).toBeDefined();
    expect(screen.getByText("证据.pdf")).toBeDefined();
    expect(screen.getByText("待审批")).toBeDefined();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/request-detail.test.tsx`
Expected: FAIL — 模块不存在。

- [ ] **Step 3: 创建 `requests/[id].tsx`** —— 导出 `ProviderLegalRequestDetailPage`。要求：
  - `useParams` 取 `requestId`。`useProviderLegalRequest(requestId)`。loading / error 态同 Task 5。
  - 顶部：返回链接 → `/provider/legal/requests`；`<h1>`「转化请求详情」；双 Badge —— 审批状态（同 Task 6 的映射）+ 订单状态（`order_status ?? '未生成'`）。
  - 请求信息卡（`.ds-card`）：案件（`owner_name` + `project_name`）、欠费金额、提交时间、申请理由（`white-space: pre-wrap`）；若 `reviewer_note` 非空展示审批意见；「订单高阶状态」一行（`order_status ?? '未生成（物业审批通过后由物业法务生成）'`）。
  - 补充材料卡：标题「补充材料」+「上传材料」按钮（hidden `<input type="file">` + `useRef`，`accept=".pdf,.png,.jpg,.jpeg"`）；上传走 `uploadRequestMaterial(requestId, file)`，成功后 `refetch()`，`uploading` 时按钮禁用 + loading；失败 `alert`/Toast 错误。
  - 材料表格：文件名、大小（`size_bytes` 格式化为 KB/MB）、上传时间、操作「下载」—— 点击 `await getMaterialDownloadUrl(requestId, m.id)` 取 url 后 `window.open(url)`。
  - 材料为空显示虚线占位「拖拽文件到此处，或点击上传（PDF / 图片，单文件 ≤ 20MB）」。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/provider/legal/__tests__/request-detail.test.tsx`
Expected: PASS。

- [ ] **Step 5: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/provider/legal/requests/\[id\].tsx frontend/src/pages/provider/legal/__tests__/request-detail.test.tsx
git commit -m "feat(§9-fe): 服务商法务-请求详情页 + 补充材料上传下载"
```

---

## Task 8: 导航 + 路由 + E2E

**Files:**
- Modify: `frontend/src/config/nav.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/e2e/per-role-pages.spec.ts`
- Test: `frontend/src/config/__tests__/nav.test.ts`

- [ ] **Step 1: 写失败测试** — `frontend/src/config/__tests__/nav.test.ts`：

```ts
import { describe, it, expect } from "vitest";
import { getNavSections } from "../nav";

describe("getNavSections — provider legal", () => {
  it("returns provider-legal nav for legal role with provider scope", () => {
    const sections = getNavSections("legal", "provider:2");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).toContain("/provider/legal/cases");
    expect(paths).toContain("/provider/legal/requests");
  });

  it("keeps property-side legal nav for legal role with tenant scope", () => {
    const sections = getNavSections("legal", "tenant:1");
    const paths = sections.flatMap((s) => s.items.map((i) => i.path));
    expect(paths).not.toContain("/provider/legal/cases");
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/config/__tests__/nav.test.ts`
Expected: FAIL — provider scope 时仍返回物业侧 legal nav。

- [ ] **Step 3: nav.ts 加 `LEGAL_PROVIDER_NAV` + scope 分支** —— 在 `nav.ts` 内，与 `PM_PROVIDER_NAV` 并列处加：

```typescript
// §9.1 — 服务商法务 nav（scope=provider:{id}）
const LEGAL_PROVIDER_NAV: NavSection[] = [
  {
    title: "我的工作",
    items: [
      { label: "法务案件", path: "/provider/legal/cases", icon: "Scale" },
      { label: "转化请求", path: "/provider/legal/requests", icon: "ClipboardList" },
    ],
  },
];
```

在 `getNavSections` 内，`project_manager` 分支之后、fallback 之前加：

```typescript
  if (role === "legal" && s.startsWith("provider:")) {
    return [...LEGAL_PROVIDER_NAV, HELP_SECTION];
  }
```

- [ ] **Step 4: App.tsx 注册 4 条路由** —— 在 `App.tsx` 顶部 import：

```typescript
import { ProviderLegalCasesPage } from "./pages/provider/legal/cases";
import { ProviderLegalCaseDetailPage } from "./pages/provider/legal/cases/[id]";
import { ProviderLegalRequestsPage } from "./pages/provider/legal/requests";
import { ProviderLegalRequestDetailPage } from "./pages/provider/legal/requests/[id]";
```

在 `<Routes>` 受保护区块内（与既有 `/provider/*` 路由并列）加：

```tsx
<Route path="/provider/legal/cases" element={<ProviderLegalCasesPage />} />
<Route path="/provider/legal/cases/:id" element={<ProviderLegalCaseDetailPage />} />
<Route path="/provider/legal/requests" element={<ProviderLegalRequestsPage />} />
<Route path="/provider/legal/requests/:id" element={<ProviderLegalRequestDetailPage />} />
```

- [ ] **Step 5: E2E 加 provider-legal 冒烟** —— `frontend/e2e/per-role-pages.spec.ts` 的 `ROLE_CASES` 里，给 `legal` 角色项的 `pages` 数组追加（若 seed 有 provider-legal 账号则新增一个角色项；否则在注释说明需 seed 账号）：

```typescript
      { path: "/provider/legal/cases", expectText: /法务案件|案件/ },
      { path: "/provider/legal/requests", expectText: /转化请求|请求/ },
```

> 注：provider-legal 账号需 seed 中存在 `legal` 角色 + `provider_id` 的用户。若 `per-role-pages.spec.ts` 现有 `legal` 账号是物业侧，则改为**新增**一个 `legal (provider)` 角色项（phone 用 seed 里对应账号）。实施时先看 seed 脚本 `poc/backend/scripts/seed_demo*.py` 是否有该账号，没有则在 E2E 文件里加 TODO 注释并仅保留 nav 单测覆盖。

- [ ] **Step 6: 跑测试确认通过 + typecheck**

Run: `cd frontend && npx vitest run src/config/__tests__/nav.test.ts && npx tsc -p tsconfig.json --noEmit`
Expected: PASS + 无类型报错。

- [ ] **Step 7: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/config/nav.ts frontend/src/config/__tests__/nav.test.ts frontend/src/App.tsx frontend/e2e/per-role-pages.spec.ts
git commit -m "feat(§9-fe): 服务商法务导航 + 路由 + E2E 冒烟"
```

---

# Part 3 — §9.2 减免 / 佣金 / 项目费率前端

## Task 9: 减免归属展示

**Files:**
- Modify: `frontend/src/pages/discount/api.ts`（`DiscountOfferDTO`）
- Modify: `frontend/src/pages/discount/ApprovalListPage.tsx`
- Modify: `frontend/src/pages/discount/ApprovalDetailPage.tsx`
- Test: `frontend/src/pages/discount/__tests__/attribution.test.tsx`

- [ ] **Step 1: 写失败测试** — `frontend/src/pages/discount/__tests__/attribution.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const baseOffer = {
  id: 1, tenant_id: 1, case_id: 1, applicant_user_id: 2, applicant_role: "agent",
  applicant_name: "王五", case_owner: "张三", case_building: "1栋101", project_name: "阳光花园",
  offer_type: "principal_discount", offer_type_label: "本金减免",
  original_amount: "1000.00", proposed_amount: "800.00", discount_pct: 20,
  installment_months: null, reason: "家庭困难", status: "pending_supervisor",
  approver_role_required: "supervisor", approved_by_user_id: null, approved_by_name: null,
  approved_at: null, rejected_reason: null, expires_at: "2026-05-24T00:00:00",
  audit_trail: [], created_at: "2026-05-17T10:00:00",
};

vi.mock("../api", () => ({
  useDiscountOffers: () => ({
    items: [
      { ...baseOffer, id: 1, provider_id: null, provider_name: null },
      { ...baseOffer, id: 2, provider_id: 5, provider_name: "信达催收" },
    ],
    total: 2, isLoading: false, refetch: vi.fn(),
  }),
}));

import { ApprovalListPage } from "../ApprovalListPage";

describe("减免归属来源展示", () => {
  it("shows 物业内勤 and 服务商 source", () => {
    render(<MemoryRouter><ApprovalListPage backTo="/" approverRole="supervisor" /></MemoryRouter>);
    expect(screen.getByText("物业内勤")).toBeDefined();
    expect(screen.getByText(/信达催收/)).toBeDefined();
  });
});
```

> 注：`ApprovalListPage` 的 props（`backTo` / `approverRole`）以现有签名为准 —— 实施前先读该文件确认 props，测试里据实传。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/discount/__tests__/attribution.test.tsx`
Expected: FAIL — 无「物业内勤」「信达催收」文本。

- [ ] **Step 3: `discount/api.ts` 加字段** —— `DiscountOfferDTO` 接口里 `case_id` 之后加：

```typescript
  provider_id: number | null;
  provider_name: string | null;
```

- [ ] **Step 4: 列表页加「来源」列** —— `ApprovalListPage.tsx` 表格 `<thead>` 加 `<th>来源</th>`（放「业主/房号」列之后），`<tbody>` 每行对应加：

```tsx
<td>
  {o.provider_id == null ? (
    <span className="ds-badge" style={{ background: "#F3F4F6", color: "#4B5563" }}>物业内勤</span>
  ) : (
    <span className="ds-badge ds-badge-blue">服务商 · {o.provider_name ?? `#${o.provider_id}`}</span>
  )}
</td>
```

- [ ] **Step 5: 详情页加「来源」行** —— `ApprovalDetailPage.tsx` 详情字段 grid 内加一个 `<Field label="来源" value={...} />`（沿用该文件已有的 `Field` 组件），value 同 Step 4 的 Badge 逻辑。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/discount/__tests__/attribution.test.tsx`
Expected: PASS。

- [ ] **Step 7: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/discount/api.ts frontend/src/pages/discount/ApprovalListPage.tsx frontend/src/pages/discount/ApprovalDetailPage.tsx frontend/src/pages/discount/__tests__/attribution.test.tsx
git commit -m "feat(§9-fe): 减免审批页展示 provider 服务商来源"
```

---

## Task 10: 服务商佣金页适配新口径

**Files:**
- Modify: `frontend/src/pages/provider/commission/index.tsx`
- Test: `frontend/src/pages/provider/__tests__/commission.test.tsx`

后端 `ProviderMemberCommission`（§9.2 后）：`commission_rate` 为加权有效率；`items[].commission_rate`（逐案项目率，Decimal string）；`items[].paid_amount` 为实收额。

- [ ] **Step 1: 写失败测试** — `frontend/src/pages/provider/__tests__/commission.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@refinedev/core", () => ({
  useCustom: () => ({
    query: {
      data: {
        data: {
          user_id: 5, name: "催收员小李", year_month: "2026-05",
          commission_rate: 0.057, base_amount: "2600.00", commission: "160.00",
          items: [
            { case_id: 1, owner_name: "张三", paid_amount: "600.00",
              paid_at: "2026-05-15T00:00:00", commission_rate: "0.1000" },
          ],
        },
      },
      isLoading: false,
    },
  }),
  useGo: () => vi.fn(),
}));

import { ProviderMemberCommissionPage } from "../commission/index";

describe("ProviderMemberCommissionPage", () => {
  it("renders weighted rate label and per-case project rate column", () => {
    render(
      <MemoryRouter initialEntries={["/provider/team/5/commission"]}>
        <ProviderMemberCommissionPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/加权有效率/)).toBeDefined();
    expect(screen.getByText("10.0%")).toBeDefined(); // 逐案项目率
  });
});
```

> 注：`ProviderMemberCommissionPage` 用 `useParams`/`useSearchParams` 取 `user_id` —— 测试在 `MemoryRouter` 提供路径即可（该页不一定需要 `Routes` 包裹，按现有实现；若用 `useParams` 则补 `Routes/Route`）。实施前读该文件确认。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/provider/__tests__/commission.test.tsx`
Expected: FAIL — 无「加权有效率」文本、无逐案项目率列。

- [ ] **Step 3: 改 `provider/commission/index.tsx`**：
  - `CommissionLineItem` 接口加 `commission_rate: string`。
  - KPI 卡「佣金费率」label 改为「加权有效率」；「计算基数（已缴费）」改为「实收基数（扣减免）」。
  - 明细表加一列「项目佣金率」：表头 `<th>` + 行内 `<td>{(Number(it.commission_rate) * 100).toFixed(1)}%</td>`。
  - 「缴费金额」列 label 改「实收金额」。
  - 其余结构不变。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/provider/__tests__/commission.test.tsx`
Expected: PASS。

- [ ] **Step 5: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/provider/commission/index.tsx frontend/src/pages/provider/__tests__/commission.test.tsx
git commit -m "feat(§9-fe): 服务商佣金页适配 §9.2 新口径（加权率+逐案项目率）"
```

---

## Task 11: 内勤提成 — api.ts + 列表页

**Files:**
- Create: `frontend/src/pages/admin/agent-commissions/api.ts`
- Create: `frontend/src/pages/admin/agent-commissions/index.tsx`
- Modify: `frontend/src/config/nav.ts`（admin nav 加「内勤提成」）
- Modify: `frontend/src/App.tsx`（route）
- Test: `frontend/src/pages/admin/agent-commissions/__tests__/list.test.tsx`

- [ ] **Step 1: 创建 `agent-commissions/api.ts`**：

```typescript
// §9.2 — 内勤提成前端 API hooks
import { useCustom } from "@refinedev/core";

export interface AgentCommissionItem {
  user_id: number;
  name: string;
  phone_masked: string;
  year_month: string;
  commission_rate: number;
  base_amount: string;
  paid_case_count: number;
  commission: string;
}

export interface AgentCommissionList {
  year_month: string;
  total_base: string;
  total_commission: string;
  items: AgentCommissionItem[];
}

export interface AgentCommissionLineItem {
  case_id: number;
  owner_name: string;
  paid_amount: string;
  paid_at: string;
  commission_rate: string;
}

export interface AgentCommissionDetail {
  user_id: number;
  name: string;
  year_month: string;
  commission_rate: number;
  base_amount: string;
  commission: string;
  items: AgentCommissionLineItem[];
}

export function useAgentCommissions(yearMonth: string) {
  const { query } = useCustom<AgentCommissionList>({
    url: "admin/agent-commissions",
    method: "get",
    config: { query: { year_month: yearMonth } },
  });
  return { data: query.data?.data, isLoading: query.isLoading };
}

export function useAgentCommissionDetail(userId: number | undefined, yearMonth: string) {
  const { query } = useCustom<AgentCommissionDetail>({
    url: userId ? `admin/agent-commissions/${userId}` : "admin/agent-commissions/0",
    method: "get",
    config: { query: { year_month: yearMonth } },
    queryOptions: { enabled: !!userId },
  });
  return { data: query.data?.data, isLoading: query.isLoading, isError: query.isError };
}
```

- [ ] **Step 2: 写失败测试** — `agent-commissions/__tests__/list.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api", () => ({
  useAgentCommissions: () => ({
    data: {
      year_month: "2026-05", total_base: "128400.00", total_commission: "7020.00",
      items: [
        { user_id: 5, name: "催收员小王", phone_masked: "138****8111", year_month: "2026-05",
          commission_rate: 0.057, base_amount: "52600.00", paid_case_count: 12, commission: "3012.00" },
      ],
    },
    isLoading: false,
  }),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { AgentCommissionsListPage } from "../index";

describe("AgentCommissionsListPage", () => {
  it("renders summary and agent row", () => {
    render(<MemoryRouter><AgentCommissionsListPage /></MemoryRouter>);
    expect(screen.getByText("催收员小王")).toBeDefined();
    expect(screen.getByText(/7,?020/)).toBeDefined();
  });
});
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/admin/agent-commissions/__tests__/list.test.tsx`
Expected: FAIL — 模块 `../index` 不存在。

- [ ] **Step 4: 创建 `agent-commissions/index.tsx`** —— 导出 `AgentCommissionsListPage`。要求（参照 `provider/commission/index.tsx` 的 KPI 卡 + 表格）：
  - `useState` 管 `ym`（默认当月 `YYYY-MM`）。`<input type="month">` 切换。
  - `useAgentCommissions(ym)`。
  - 页头「内勤提成」+ 副标题「物业内部催收员当月提成（逐案实收 × 项目内勤佣金率）」。
  - 两张 KPI 卡：当月总实收基数 `¥{total_base}`、当月总应发提成 `¥{total_commission}`。
  - 表格列：催收员（`name` + 小字 `phone_masked`）、已结案数（`paid_case_count`）、实收基数（`¥{base_amount}`）、加权佣金率（`{(commission_rate*100).toFixed(1)}%`）、应发提成（`¥{commission}`）、操作「查看明细」→ `go({ to: '/admin/agent-commissions/' + user_id + '?ym=' + ym })`。
  - 加载态「加载中…」；空「本月无内勤催收员提成数据」。

- [ ] **Step 5: nav + route** ——
  - `nav.ts`：`NAV_CONFIG.admin` 内，「减免大额审批」项之后加 `{ label: "内勤提成", path: "/admin/agent-commissions", icon: "Wallet" }`。
  - `App.tsx`：import `AgentCommissionsListPage` from `./pages/admin/agent-commissions`，加 `<Route path="/admin/agent-commissions" element={<AgentCommissionsListPage />} />`。

- [ ] **Step 6: 跑测试确认通过 + typecheck**

Run: `cd frontend && npx vitest run src/pages/admin/agent-commissions/__tests__/list.test.tsx && npx tsc -p tsconfig.json --noEmit`
Expected: PASS + 无类型报错。

- [ ] **Step 7: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/admin/agent-commissions/api.ts frontend/src/pages/admin/agent-commissions/index.tsx frontend/src/pages/admin/agent-commissions/__tests__/list.test.tsx frontend/src/config/nav.ts frontend/src/App.tsx
git commit -m "feat(§9-fe): 内勤提成列表页 + 导航 + 路由"
```

---

## Task 12: 内勤提成 — 单人明细页

**Files:**
- Create: `frontend/src/pages/admin/agent-commissions/[id].tsx`
- Modify: `frontend/src/App.tsx`（route）
- Test: `frontend/src/pages/admin/agent-commissions/__tests__/detail.test.tsx`

- [ ] **Step 1: 写失败测试** — `agent-commissions/__tests__/detail.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../api", () => ({
  useAgentCommissionDetail: () => ({
    data: {
      user_id: 5, name: "催收员小王", year_month: "2026-05",
      commission_rate: 0.057, base_amount: "52600.00", commission: "3012.00",
      items: [
        { case_id: 1, owner_name: "张三", paid_amount: "600.00",
          paid_at: "2026-05-15T00:00:00", commission_rate: "0.0800" },
      ],
    },
    isLoading: false, isError: false,
  }),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { AgentCommissionDetailPage } from "../[id]";

describe("AgentCommissionDetailPage", () => {
  it("renders agent name and per-case rate", () => {
    render(
      <MemoryRouter initialEntries={["/admin/agent-commissions/5?ym=2026-05"]}>
        <Routes>
          <Route path="/admin/agent-commissions/:id" element={<AgentCommissionDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(/催收员小王/)).toBeDefined();
    expect(screen.getByText("8.0%")).toBeDefined();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/admin/agent-commissions/__tests__/detail.test.tsx`
Expected: FAIL — 模块不存在。

- [ ] **Step 3: 创建 `agent-commissions/[id].tsx`** —— 导出 `AgentCommissionDetailPage`。要求：
  - `useParams` 取 `userId = Number(id)`；`useSearchParams` 取 `ym`（缺省当月）。
  - `useAgentCommissionDetail(userId, ym)`。loading / error 态。
  - 顶部返回链接 → `/admin/agent-commissions`；`<h1>`「内勤提成明细 · {name}」+ 副标题「{ym} · 逐案『实收 × 项目内勤佣金率』」。
  - 三张 KPI 卡：实收基数（扣已执行减免）`¥{base_amount}`、加权佣金率 `{(commission_rate*100).toFixed(1)}%`、应发提成 `¥{commission}`。
  - 表格列：案件（业主 `owner_name`）、项目佣金率（`{(Number(commission_rate)*100).toFixed(1)}%`）、实收金额（`¥{paid_amount}`）、缴清时间（`paid_at` 截 10 位）。
  - 空「本月该催收员无已结案件」。

- [ ] **Step 4: route** —— `App.tsx` import `AgentCommissionDetailPage` from `./pages/admin/agent-commissions/[id]`，加 `<Route path="/admin/agent-commissions/:id" element={<AgentCommissionDetailPage />} />`。

- [ ] **Step 5: 跑测试确认通过 + typecheck**

Run: `cd frontend && npx vitest run src/pages/admin/agent-commissions/__tests__/detail.test.tsx && npx tsc -p tsconfig.json --noEmit`
Expected: PASS + 无类型报错。

- [ ] **Step 6: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/admin/agent-commissions/\[id\].tsx frontend/src/pages/admin/agent-commissions/__tests__/detail.test.tsx frontend/src/App.tsx
git commit -m "feat(§9-fe): 内勤提成单人逐案明细页"
```

---

## Task 13: D1 — 物业项目内勤佣金率字段

**Files:**
- Modify: `frontend/src/pages/admin/projects/new.tsx`
- Modify: `frontend/src/pages/admin/projects/edit.tsx`
- Test: `frontend/src/pages/admin/projects/__tests__/commission-rate-field.test.tsx`

后端 `ProjectCreateIn`/`ProjectUpdateIn.internal_agent_commission_rate` 为 **0–1 小数**（可空）；`ProjectOut` 另含 `provider_agent_commission_rate`（只读）。表单按百分比录入。

- [ ] **Step 1: 写失败测试** — `admin/projects/__tests__/commission-rate-field.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@refinedev/core", () => ({
  useGo: () => vi.fn(),
  useCreate: () => ({ mutate: vi.fn(), mutation: { isPending: false } }),
}));

import { AdminProjectNewPage } from "../new";

describe("项目创建表单 — D1 内勤佣金率", () => {
  it("renders the internal-agent commission rate field", () => {
    render(<MemoryRouter><AdminProjectNewPage /></MemoryRouter>);
    expect(screen.getByText(/内勤催收员佣金率/)).toBeDefined();
  });
});
```

> 注：`AdminProjectNewPage` 实际依赖的 hooks 以现有 import 为准（可能还有 `useList` 拉 PM 候选等）。实施前读 `new.tsx`，把测试的 `vi.mock("@refinedev/core", ...)` 补全到该页用到的所有 Refine hooks，避免渲染崩溃。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/admin/projects/__tests__/commission-rate-field.test.tsx`
Expected: FAIL — 无「内勤催收员佣金率」字段。

- [ ] **Step 3: `new.tsx` 加字段**：
  - 加 state：`const [internalCommRate, setInternalCommRate] = useState("");`（百分比字符串）。
  - 在「减免审批策略」表单区附近加一个 `.form-group`：label「内勤催收员佣金率 (%)」+ `<input className="form-control" type="number" min="0" max="100" step="0.01">`，`.form-hint`「留空 = 继承系统默认 5%」。
  - `submit()` 的 `values` 里加：`internal_agent_commission_rate: internalCommRate === "" ? null : Number(internalCommRate) / 100`。

- [ ] **Step 4: `edit.tsx` 同样加字段** —— 加同一字段；初始化时把后端的 `internal_agent_commission_rate`（0–1）× 100 填入输入框；提交同样 ÷100。另外**只读展示** `provider_agent_commission_rate`：一行 `.form-hint` 或禁用输入框「服务商佣金率：{rate==null ? '继承默认 5%' : (rate*100).toFixed(2)+'%'}（由服务商设置，物业不可改）」。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/admin/projects/__tests__/commission-rate-field.test.tsx`
Expected: PASS。

- [ ] **Step 6: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/admin/projects/new.tsx frontend/src/pages/admin/projects/edit.tsx frontend/src/pages/admin/projects/__tests__/commission-rate-field.test.tsx
git commit -m "feat(§9-fe): D1 物业项目表单加内勤佣金率字段"
```

---

## Task 14: D2 — 服务商项目佣金率编辑

**Files:**
- Modify: `frontend/src/pages/provider/projects/index.tsx`
- Test: `frontend/src/pages/provider/__tests__/project-commission-rate.test.tsx`

后端 `PATCH /api/v1/provider/projects/{project_id}/commission-rate` body `{provider_agent_commission_rate}`（0–1 小数）。`provider/projects` 列表的 item 需含 `provider_agent_commission_rate`（后端 `provider/projects` 若未透出该字段，按 §9.2 spec `ProjectOut` 已含 —— 实施前确认 `provider/projects` 端点返回字段；若缺则该列显示「—」并仅靠编辑写入）。

- [ ] **Step 1: 写失败测试** — `provider/__tests__/project-commission-rate.test.tsx`：

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@refinedev/core", () => ({
  useCustom: () => ({
    query: {
      data: { data: { items: [
        { project_id: 1, project_name: "阳光花园", tenant_name: "金桂物业",
          plan_start: null, plan_end: null, provider_pm_user_id: null, provider_pm_name: null,
          provider_agent_commission_rate: "0.1000" },
      ] } },
      refetch: vi.fn(),
    },
  }),
  useCustomMutation: () => ({ mutate: vi.fn(), mutation: { isPending: false } }),
  useList: () => ({ query: { data: { data: [] } } }),
}));

import { ProviderProjectsPage } from "../../provider/projects/index";

describe("服务商项目 — D2 佣金率列", () => {
  it("renders the commission rate column", () => {
    render(<MemoryRouter><ProviderProjectsPage /></MemoryRouter>);
    expect(screen.getByText(/服务商佣金率/)).toBeDefined();
    expect(screen.getByText("10.0%")).toBeDefined();
  });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/pages/provider/__tests__/project-commission-rate.test.tsx`
Expected: FAIL — 无「服务商佣金率」列。

- [ ] **Step 3: 改 `provider/projects/index.tsx`**：
  - `ProviderProjectItem` 接口加 `provider_agent_commission_rate: string | null`。
  - 表格加列「服务商佣金率」：`<th>` + 行内 `{p.provider_agent_commission_rate == null ? "继承默认 5%" : (Number(p.provider_agent_commission_rate) * 100).toFixed(1) + "%"}`。
  - 操作列加按钮「设置佣金率」→ 打开 `CommissionRateModal`（参照同文件 `AssignPmModal`）。
  - `CommissionRateModal`：一个 `<input type="number" min="0" max="100" step="0.01">`（百分比）；保存调 `useCustomMutation().mutate({ url: 'provider/projects/' + project_id + '/commission-rate', method: 'patch', values: { provider_agent_commission_rate: Number(input)/100 } }, { onSuccess, onError })`；成功后 `refetch()` + 关闭。
  - 同时只读展示「内勤佣金率」（若 item 含 `internal_agent_commission_rate`）：列或 modal 内一行小字「内勤佣金率由物业设置，服务商不可改」。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd frontend && npx vitest run src/pages/provider/__tests__/project-commission-rate.test.tsx`
Expected: PASS。

- [ ] **Step 5: lint + commit**

```bash
cd frontend && npm run lint
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/provider/projects/index.tsx frontend/src/pages/provider/__tests__/project-commission-rate.test.tsx
git commit -m "feat(§9-fe): D2 服务商项目佣金率列 + 编辑弹窗"
```

---

## Task 15: 全量回归 + lint + 标注 spec

**Files:**
- Modify: `docs/superpowers/specs/2026-05-17-section9-frontend-ui-design.md`（标注完成）

- [ ] **Step 1: 前端全量测试**

Run: `cd frontend && npx vitest run`
Expected: 全绿（既有测试 + §9 新增）。失败若由 §9 改动引入则修复（改/补测试）；若无关既有问题，如实记录。

- [ ] **Step 2: 前端 lint + typecheck**

Run: `cd frontend && npm run lint && npx tsc -p tsconfig.json --noEmit`
Expected: 零 error、零 `any`。

- [ ] **Step 3: 后端全量回归**

Run: `cd poc/backend && python3.12 -m pytest -q`
Expected: 全绿（含 Task 1/2 改动）。

- [ ] **Step 4: 后端 lint**

Run: `cd poc/backend && python3.12 -m ruff check app/schemas/discount.py app/api/discount_offers.py app/api/admin.py`
Expected: All checks passed。

- [ ] **Step 5: 标注 spec 完成** —— `docs/superpowers/specs/2026-05-17-section9-frontend-ui-design.md` 末尾加一行：

```markdown

---

> ✅ **已实现(2026-05-17)**：§9.1 服务商法务 4 页 + 导航/路由；§9.2 减免归属展示、服务商佣金页适配、内勤提成列表+详情、D1/D2 项目佣金率；配套 3 处后端改动。见实施计划 `docs/superpowers/plans/2026-05-17-section9-frontend-ui.md`。
```

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add docs/superpowers/specs/2026-05-17-section9-frontend-ui-design.md
git commit -m "docs(§9-fe): 标注 §9 前端 UI 已实现"
```

---

## Self-Review

**Spec 覆盖（逐条核对 `2026-05-17-section9-frontend-ui-design.md`）：**
- §3 文件结构 → File Structure 章 + 各 task ✅
- §4.1 案件列表 → Task 4 ✅；§4.2 案件详情+发起请求 → Task 5 ✅（§4.2 互斥横幅按 DTO 现实简化，已注明）；§4.3 请求列表 → Task 6 ✅；§4.4 请求详情+材料 → Task 7 ✅；§4.5 导航 → Task 8 ✅
- §5.1 减免归属 → Task 9 ✅；§5.2 服务商佣金页 → Task 10 ✅；§5.3 内勤提成 2 页 → Task 11+12 ✅；§5.4 D1 → Task 13 ✅；§5.5 D2 → Task 14 ✅
- §6 配套后端 3 处 → Task 1（provider_name）+ Task 2（detail 算法 + commission_rate）✅
- §7 数据流 / §8 状态·权限 → 关键约定章 + 各 task 的加载/空/错误要求 ✅
- §9 测试 → 每个 task 含 Vitest 测试 + Task 8 E2E + Task 15 全量回归 ✅

**占位符扫描：** 无 TBD/TODO。少数 task（9/10/13/14）含「实施前读该文件确认 props/字段」—— 这是针对现有文件真实签名的必要核对指令，非占位符；已给出确认对象与兜底做法。

**类型一致性：** `provider/legal/api.ts` 的类型（`ProviderLegalCaseListItem` 等）与后端 `provider_legal.py` schema 字段逐一对应；`agent-commissions/api.ts` 的 `AgentCommissionLineItem.commission_rate` 与 Task 2 后端新增字段一致；D1/D2 佣金率前端百分比 ÷100、后端 0–1 小数，三处（Task 13/14 提交、Task 10/12 展示 ×100）口径一致。

**已知简化（非缺口）：** §4.2 案件详情的「已有请求」互斥横幅取消 —— `ProviderLegalCaseDetail` 后端 DTO 无请求关联字段，改为「按钮常驻 + 后端错误响应兜底」，spec §4.2 已明确允许此口径。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-17-section9-frontend-ui.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 每个 task 派新 subagent 实现，task 间两段式 review（spec 合规 → 代码质量），快速迭代。

**2. Inline Execution** — 本会话内按 executing-plans 分批执行，批次间设检查点。

Which approach?
