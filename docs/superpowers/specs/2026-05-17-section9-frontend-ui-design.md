# §9 配套前端 UI 设计文档

> §9 三项下游需求的后端能力（§9.1 服务商法务、§9.2 减免归属+审批流+佣金、§9.3 WS 广播脱敏）已实现并合并上线（见 `main`）。本设计为其补齐配套前端 UI。

**日期：** 2026-05-17
**分支：** `feat/section9-frontend-ui`（实施时创建）
**来源 spec：** `2026-05-16-provider-legal-boundary-design.md`、`2026-05-16-discount-attribution-commission-design.md`、`2026-05-16-ws-broadcast-phone-masking-design.md`

---

## 1. 背景

§9 三项后端能力已交付，但当时明确「只交付后端、不动前端」。现在补配套 PC 前端：

- **§9.1 服务商法务** —— 后端新增 `/api/v1/provider/legal/*` 7 个端点，前端**完全没有** provider-legal 页面。
- **§9.2 减免归属 + 佣金** —— 减免审批页、服务商佣金页已存在但未适配 §9.2 新口径；内勤提成、项目佣金率配置无 UI。
- **§9.3 WS 广播脱敏** —— 脱敏在服务端完成，**无前端 UI 面**，不在本设计范围。

## 2. 范围

**本轮做：** §9.1 服务商法务全套新页面 + §9.2 减免/佣金/项目费率全部前端增改，合并为一个 spec / 一个实施计划。

**设计方向：** 沿用现有项目整体风格 —— shadcn/ui + Tailwind + 蓝色 token（`color-primary #1A56DB`），严格遵守 `docs/DESIGN_SPEC.md`。不引入新视觉语言。

**OUT of scope：** §9.3 相关 UI（无 UI 面）；§9.2b 的物业付服务商服务费率、服务商结算单生成；任何与 §9 无关的页面重构。

## 3. 架构与文件结构

PC 前端单子项目（`frontend/`，TypeScript + React + Refine.dev v5 + shadcn/ui）。另含 3 处**配套小后端改动**（§6）—— 为前端展示所必需，随本轮一起做。

### 3.1 新建文件

```
frontend/src/pages/provider/legal/
├── api.ts                — Refine useCustom/useCustomMutation hooks + DTO 类型
├── cases/
│   ├── index.tsx         — 法务案件浏览列表
│   └── [id].tsx          — 案件详情（主操作：发起法务转化请求）
└── requests/
    ├── index.tsx         — 转化请求列表（状态跟踪）
    └── [id].tsx          — 请求详情（订单高阶状态 + 补充材料上传/下载）

frontend/src/pages/admin/agent-commissions/
├── api.ts                — 内勤提成 hooks + DTO 类型
├── index.tsx             — 内勤提成列表
└── [id].tsx              — 单人逐案明细
```

### 3.2 修改文件

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/discount/api.ts` | `DiscountOfferDTO` 加 `provider_id` + `provider_name` |
| `frontend/src/pages/discount/ApprovalListPage.tsx` | 加「来源」列 |
| `frontend/src/pages/discount/ApprovalDetailPage.tsx` | 加「来源」行 |
| `frontend/src/pages/provider/commission/index.tsx` | 适配 §9.2 新口径（加权率 / 逐案率 / 实收） |
| `frontend/src/pages/admin/projects/new.tsx` | 加 D1「内勤佣金率」字段 |
| `frontend/src/pages/admin/projects/edit.tsx` | 加 D1 字段 + D2 率只读展示 |
| `frontend/src/pages/provider/projects/index.tsx` | 加 D2「服务商佣金率」列 + 编辑入口 |
| `frontend/src/config/nav.ts` | 新增 `LEGAL_PROVIDER_NAV`；admin nav 加「内勤提成」 |
| `frontend/src/App.tsx` | 注册 6 个新路由 |

## 4. §9.1 服务商法务 — 四个页面

四个页面统一套在标准 TopBar 56px + SideNav 240px 外壳内（DESIGN_SPEC §3.1），用现有 DataTable / Card / Badge / Dialog / Skeleton 组件。仅 `role=legal` + `scope=provider:` 可见可访问。

### 4.1 法务案件浏览列表 — `cases/index.tsx`

- 后端：`GET /api/v1/provider/legal/cases`（`PaginatedResponse[ProviderLegalCaseListItem]`）。
- 页面标题「法务案件」+ 说明「浏览本服务商承接项目下的案件（只读，手机号脱敏）」。
- 项目筛选 Select + 业主/房号搜索框。
- DataTable 列：业主/房号（含脱敏手机号）、项目、欠费金额、逾期月数、案件阶段（Badge）、操作（查看）。
- 服务端分页，筛选条件存 URL query。只读 —— 无任何写操作。

### 4.2 案件详情 — `cases/[id].tsx`

- 后端：`GET /api/v1/provider/legal/cases/{case_id}`（`ProviderLegalCaseDetail`）；`POST /api/v1/provider/legal/cases/{case_id}/conversion-request`。
- 返回链接 + 标题「案件详情 · {房号} {业主}」。
- 案件信息卡：业主、脱敏手机号、项目、房号、欠费金额、逾期、案件阶段、最近跟进、承接服务商；跟进摘要（只读）。
- 右上主按钮「发起法务转化请求」→ 点击弹 `<Dialog>` 填申请理由（`reason`，必填，多行文本）→ 提交 POST → 成功 Toast + 跳转该请求详情页。
- 互斥横幅：若该案件已有**在途**转化请求（待审批 / 已通过），顶部出蓝色信息横幅「本案件已于 {date} 发起转化请求（{状态}）— 查看请求」，主按钮置灰禁用（避免重复发起）；无请求、或仅有已驳回 / 已取消的历史请求时，横幅隐藏、按钮可点（允许重新发起）。
- 该状态依据案件详情接口返回的请求关联信息判定；若后端另有去重约束，以其错误响应为准并 Toast 提示。实施时按 `ProviderLegalCaseDetail` 实际字段确定取数方式。

### 4.3 转化请求列表 — `requests/index.tsx`

- 后端：`GET /api/v1/provider/legal/conversion-requests`（`PaginatedResponse[ProviderLegalRequestOut]`）。
- 标题「法务转化请求」+ 说明。
- DataTable 列：案件（业主/房号）、项目、申请理由（摘要）、审批状态（Badge：待审批 warning / 已通过 success / 已驳回 danger / 已取消 neutral）、订单状态（Badge）、提交时间、操作（查看）。
- 服务端分页。

### 4.4 转化请求详情 — `requests/[id].tsx`

- 后端：`GET /api/v1/provider/legal/conversion-requests/{request_id}`（`ProviderLegalRequestDetail`，含 `order_status` + `materials[]`）；`POST .../materials`；`GET .../materials/{material_id}`（下载链接）。
- 返回链接 + 标题「转化请求详情」。
- 顶部双 Badge：审批状态 + 订单高阶状态。
- 请求信息卡：案件快照、申请人、提交时间、申请理由；若已审批含审批人意见。
- 「订单高阶状态」区：展示 `order_status`（物业审批通过后由物业法务生成订单，未生成时显示「未生成」）。
- 「补充材料」区：拖拽 / 点击上传（PDF / 图片，单文件 ≤ 20MB，走项目现有文件上传机制）；材料 DataTable（文件名、大小、上传时间、下载）。下载按钮调 `GET .../materials/{id}` 取临时链接后触发浏览器下载。

### 4.5 导航 `LEGAL_PROVIDER_NAV`

`src/config/nav.ts` 新增服务商法务导航段，机制对标现有 `PM_PROVIDER_NAV`：`getNavForRole` 中 `role=legal` 且 `scope` 以 `provider:` 开头 → 返回 `LEGAL_PROVIDER_NAV`，否则维持现有物业侧 `legal` 导航。菜单项：

```
法务案件      /provider/legal/cases       icon: Scale
转化请求      /provider/legal/requests    icon: ClipboardList
```

## 5. §9.2 前端增改

### 5.1 减免归属展示 — `src/pages/discount/`

- `api.ts` 的 `DiscountOfferDTO` 加 `provider_id: number | null` + `provider_name: string | null`。
- `ApprovalListPage.tsx` 加「来源」列、`ApprovalDetailPage.tsx` 加「来源」行：Badge —— `provider_id` 为 `null` → `物业内勤`；非空 → `服务商 · {provider_name}`。
- 减免审批端点（approve/reject/escalate）§9.2-B 已收紧为物业侧专属；审批页本就是 supervisor/admin 页面，**结构无需改**。

### 5.2 服务商佣金页 — `src/pages/provider/commission/index.tsx`

- 后端 `GET /api/v1/provider/team/{member_user_id}/commission`（`ProviderMemberCommission`）§9.2 后口径已变：
  - 顶部 `commission_rate` 改标「加权有效率」。
  - `base_amount` 标注「实收基数（扣已执行减免）」。
  - 逐案明细表加「项目佣金率」列（`CommissionLineItem.commission_rate`，§9.2 已加该字段）；`paid_amount` 标注为「实收金额」。
- 纯前端改动。

### 5.3 内勤提成（新建 2 页） — `src/pages/admin/agent-commissions/`

- **列表 `index.tsx`** —— 后端 `GET /api/v1/admin/agent-commissions?year_month=YYYY-MM`（`AgentCommissionList`）。月份选择器（默认当月）+ 两张统计卡（当月总实收基数 / 当月总应发提成）+ DataTable（催收员姓名+脱敏手机号、已结案数、实收基数、加权佣金率、应发提成、查看明细）。
- **详情 `[id].tsx`** —— 后端 `GET /api/v1/admin/agent-commissions/{user_id}?year_month=YYYY-MM`（`AgentCommissionDetail`）。三张统计卡（实收基数 / 加权佣金率 / 应发提成）+ 逐案 DataTable（案件业主·房号、项目佣金率、实收金额、缴清时间）。
- 物业 `admin` 角色可见可访问。

### 5.4 D1 物业项目内勤佣金率 — `admin/projects/new.tsx` + `edit.tsx`

- 项目表单加「内勤催收员佣金率」字段：百分比输入（0–100%），可空 = 继承系统默认 5%；放在既有「减免阈值」区附近。提交映射到 `ProjectCreateIn` / `ProjectUpdateIn.internal_agent_commission_rate`（后端字段为 0–1 小数，前端百分比 ÷100 后提交）。
- `edit.tsx` 额外**只读展示**「服务商佣金率」（`ProjectOut.provider_agent_commission_rate`，物业可见不可改，§9.2 spec §6.4）。

### 5.5 D2 服务商项目佣金率 — `provider/projects/index.tsx`

- 项目列表加「服务商佣金率」列；行内「编辑」按钮 → `<Dialog>` 百分比数字输入 → `PATCH /api/v1/provider/projects/{project_id}/commission-rate`（body `provider_agent_commission_rate`，0–1 小数）。
- 同时只读展示「内勤佣金率」（服务商可见不可改）。

## 6. 配套后端改动

为前端展示所必需的 3 处小改动，随本轮一起做，按 CLAUDE.md「先写测试」补/改 pytest 用例：

1. **`DiscountOfferOut` 加 `provider_name`** —— `app/schemas/discount.py` 加字段；`app/api/discount_offers.py` 的 `_to_out` 按 `offer.provider_id` 查 `ServiceProvider.name` 补 enrich（与现有 `applicant_name` / `project_name` 同写法）。
2. **`get_agent_commission_detail` 迁 §9.2 新算法** —— `app/api/admin.py` 的详情端点当前仍是旧口径（固定 0.05、不扣减免、不按项目率）。改为镜像 `list_agent_commissions`：逐案「实收（扣已执行减免）× 项目内勤率」，复用 `app/services/commission.py`。
3. **`AgentCommissionLineItem` 加 `commission_rate`** —— `app/api/admin.py` 内该 schema 加 `commission_rate: Decimal` 字段，详情端点逐案填入项目内勤率，与服务商 `CommissionLineItem.commission_rate` 对齐。

## 7. 数据流

- §9 端点均为非 resource 自定义路径，沿用现有 `discount/api.ts` / `provider/commission` 写法：`useCustom`（GET 列表/详情）+ `useCustomMutation`（POST 发起请求、上传材料、PATCH 佣金率）。
- 列表分页：`useCustom` 传 `page` / `page_size`，后端返 `PaginatedResponse`；筛选与分页状态同步进 URL query（刷新不丢）。
- 材料上传：multipart POST，复用项目现有文件上传机制（合同附件 / 法务文档已有同类实现）。
- 每个新 `api.ts` 显式声明 DTO 类型，禁止 `any`。

## 8. 加载 / 错误 / 空状态 / 权限

严格按 DESIGN_SPEC §2.4：

- **加载**：表格 / 卡片用 `<Skeleton>`（≥500ms 才显示，避免闪烁）。
- **错误**：`<Toast>` + 后端具体 `message`（错误响应为扁平 `{code,message}`）。
- **空**：统一空状态组件，区分「无数据」与「搜索无结果」。
- **提交中**：按钮 loading + 禁用，防重复提交。
- **权限**：§9.1 四页 `role=legal` + `scope=provider:` 才可见，接 Refine `accessControlProvider`，导航对其他角色隐藏，越权访问 `/provider/legal/*` 落 403 页；`/admin/agent-commissions` 与 D1 表单限物业 `admin`；D2 编辑限服务商 `project_manager` / `admin`。
- **手机号**：后端已按权限脱敏返回，前端直接展示，不二次处理。

## 9. 测试

- **组件测试**（Vitest + React Testing Library）：每个新页面测渲染、加载/空/错误三态、关键交互（发起转化请求 Dialog 提交、材料上传、D2 佣金率编辑 Dialog、月份切换）。对标现有 `provider/__tests__`、`calls/__tests__` 写法，Refine 数据 hook 用 mock。
- **E2E**（Playwright）：4 个 provider-legal 页面纳入 `frontend/e2e/per-role-pages.spec.ts` 冒烟；新增 1 条 happy-path —— 服务商法务发起转化请求全流程。
- **后端**（pytest + testcontainers）：§6 三处改动先写/改测试再实现。
- **验收**：前端 eslint 零 `any` + 后端 ruff 全绿；前后端全量测试绿。

## 10. 文件清单

| 文件 | 操作 |
|------|------|
| `frontend/src/pages/provider/legal/api.ts` | 建 |
| `frontend/src/pages/provider/legal/cases/index.tsx` | 建 |
| `frontend/src/pages/provider/legal/cases/[id].tsx` | 建 |
| `frontend/src/pages/provider/legal/requests/index.tsx` | 建 |
| `frontend/src/pages/provider/legal/requests/[id].tsx` | 建 |
| `frontend/src/pages/admin/agent-commissions/api.ts` | 建 |
| `frontend/src/pages/admin/agent-commissions/index.tsx` | 建 |
| `frontend/src/pages/admin/agent-commissions/[id].tsx` | 建 |
| `frontend/src/pages/discount/api.ts` | 改 |
| `frontend/src/pages/discount/ApprovalListPage.tsx` | 改 |
| `frontend/src/pages/discount/ApprovalDetailPage.tsx` | 改 |
| `frontend/src/pages/provider/commission/index.tsx` | 改 |
| `frontend/src/pages/admin/projects/new.tsx` | 改 |
| `frontend/src/pages/admin/projects/edit.tsx` | 改 |
| `frontend/src/pages/provider/projects/index.tsx` | 改 |
| `frontend/src/config/nav.ts` | 改 |
| `frontend/src/App.tsx` | 改 |
| `poc/backend/app/schemas/discount.py` | 改（`provider_name`） |
| `poc/backend/app/api/discount_offers.py` | 改（`_to_out` enrich） |
| `poc/backend/app/api/admin.py` | 改（detail 迁新算法 + `AgentCommissionLineItem.commission_rate`） |
| `frontend/src/pages/**/__tests__/`、`frontend/e2e/`、`poc/backend/tests/` | 建/改测试 |

无 Android 改动。
