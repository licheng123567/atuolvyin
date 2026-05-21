# 缴费链接 + 收款配置 设计方案

> 状态：设计稿，待评审
> 日期：2026-05-19
> 关联：PRD §14「支付功能」、UI_GAPS.md 第 27 行（支付二维码暂缓 v1.1）

## 1. 背景与目标

当前「发送缴费链接」（v2.2 Item 2）只生成一个占位 URL + 二维码弹窗 + 审计日志：

- 链接域名、token 全是硬编码占位，token 不入库；
- 业主扫码打开是空的（H5 落地页不存在）；
- 没有任何收款信息配置，也没有支付明细。

本方案把它补成可用的闭环：物业管理单位**按项目**配置自己的收款信息，催收人员点「发送缴费链接」生成业主专属二维码 / 短链，业主扫码看到一个带**支付明细构成**（应缴 − 已减免 = 应支付）的 H5 静态账单页，按页面展示的线下方式缴费。

**MVP 不接在线支付**；公证提存 + 在线支付通道作为 v1.1 扩展，本方案预留模型但不实现。

## 2. 范围

| 阶段 | 内容 |
|---|---|
| **MVP（本方案）** | 项目级收款配置（模式 A 物业自收）、`payment_link` 持久化、发送链接返回支付明细、弹窗展示明细、业主 H5 静态账单页、减免联动读取、待审批减免非阻断提醒 |
| **v1.1（仅预留，不实现）** | 模式 B 公证提存、微信/支付宝服务商在线支付通道、支付回调自动标「已缴费」、平台公证提存白名单 |

## 3. 核心模型：收款模式挂在项目上

`Project` 新增字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `payment_mode` | `str` | `property_self`（默认，模式 A）/ `notary_escrow`（模式 B，v1.1）|
| `payee_name` | `str \| None` | 收款户名，如「××物业管理有限公司」|
| `payee_account` | `str \| None` | 收款账户，自由文本（银行名 + 卡号 / 对公账户）|
| `payee_qr_object_key` | `str \| None` | 收款码图（微信/支付宝收款码）在 MinIO 的 object key，可空 |
| `payment_instructions` | `str \| None` | 线下缴费说明，自由文本多行（缴费时间、到物业服务中心地址、备注「转账请注明房号」等）|

**配置归属（用户已确认按项目级）：**

- **物业管理员** 在项目编辑页（`/admin/projects/:id/edit`）配置上述 4 个收款字段；每个项目独立配置。
- **平台超管** 控制 `payment_mode` 是否允许选 `notary_escrow`（v1.1 的白名单）；MVP 阶段 `payment_mode` 固定 `property_self`，前端不展示模式选择。

`ProjectCreateIn` / `ProjectUpdateIn` 增加这 4 个收款字段（`payment_mode` MVP 阶段服务端忽略入参、固定 `property_self`）。

## 4. payment_link 持久化

新表 `payment_link` —— token 与案件的映射，业主 H5 页凭 token 查案件：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger PK | |
| `token` | `str` unique index | `secrets.token_urlsafe(12)` |
| `tenant_id` | FK tenant | 租户隔离 |
| `case_id` | FK collection_case | |
| `project_id` | FK project \| None | 取案件所属项目，H5 渲染收款信息用 |
| `created_by_user_id` | FK user_account | 发送人 |
| `payment_mode` | `str` | 发送时项目的 `payment_mode` 快照 |
| `created_at` | datetime | |
| `expires_at` | datetime | 默认 created_at + 7 天 |

同一案件多次发送 → 每次新建一行（token 不复用，便于审计区分；旧 token 到期自然失效）。

## 5. 支付明细构成 + 减免联动（用户问题的核心）

### 5.1 明细数据来源

`CollectionCase` 已有 `principal_amount`（本金）、`late_fee_amount`（违约金/滞纳金）、`amount_owed`（应缴合计）。

减免来自 `DiscountOffer` 表（`case_id`、`original_amount`、`proposed_amount`、`status`、`expires_at`）。
**有效减免** = 该案件 `status='approved'` 且 `expires_at > now()` 的 `DiscountOffer`，多条取 `approved_at` 最新一条。

### 5.2 计算规则 —— 共享 helper `compute_payable(db, case)`

```
original  = case.amount_owed
若存在有效减免 offer:
    payable = offer.proposed_amount
    waived  = original - payable
否则:
    payable = original
    waived  = 0
has_pending = 该案件存在 status ∈ ('pending_supervisor','pending_admin') 的 DiscountOffer
```

返回 `{ principal, late_fee, original, waived, payable, has_pending }`。

### 5.3 明细在 H5 / 弹窗的呈现

```
物业费本金            ¥ principal_amount
违约金 / 滞纳金        ¥ late_fee_amount
──────────────────────────────
应缴合计              ¥ original
已减免               - ¥ waived          ← waived = 0 时此行不显示
══════════════════════════════
应支付               ¥ payable
```

### 5.4 减免联动是「读取」关系

发送链接**不产生**减免，只读取案件当前**已审批通过**的减免算出 `payable`。取值时机：

- **模式 A（线下，MVP）**：H5 页**实时计算**（用户确认）。减免审批通过后业主刷新即见降后金额，无需重发链接。`payment_link` 行只存 token→case 映射，不冻结金额。
- **模式 B（在线支付，v1.1）**：业主点「去支付」时锁定金额生成支付单。

### 5.5 待审批减免非阻断提醒（用户确认）

催收员点「发送缴费链接」时若 `has_pending=true`，发送**照常成功**，仅在弹窗顶部加一条提示：
> ⚠ 该案件有待审批减免，当前链接金额按已审批结果计算（¥payable）；减免审批通过后业主刷新链接即见更新。

## 6. 后端 API

### 6.1 扩展现有发送端点

`POST /agent/cases/{id}/send-payment-link`（坐席）与 `POST /admin/cases/{id}/send-payment-link`（管理员/督导）：

- 改为写入 `payment_link` 行（token 持久化）；
- 响应在原 `{case_id, link, short_link, sent_to, sent_at, expires_at, sms_status}` 基础上增加 `breakdown`（§5.2 的 `compute_payable` 结果）。

`app/services/payment_link.py` 的 `build_and_record_payment_link` 相应改造：建 `payment_link` 行 + 调 `compute_payable` + 返回扩展后的 schema。

### 6.2 新增业主公开端点

`GET /public/payment/{token}` —— **无需登录**，业主 H5 页调用：

- 按 token 查 `payment_link`，校验 `expires_at > now()`，过期返回 410；
- 实时跑 `compute_payable`（§5.4 模式 A 实时计算）；
- 返回 `{ project_payee: {payee_name, payee_account, payee_qr_url, payment_instructions}, owner_name, owner_room, breakdown, payment_mode, expired }`；
- **不返回手机号**（PRD §14 防泄露）；`payee_qr_url` 为 MinIO 预签名 URL。

挂在一个不带鉴权依赖的 `public` router。

## 7. 前端

### 7.1 项目编辑页 —— 收款配置

`frontend/src/pages/admin/projects/edit.tsx`（及 `new.tsx`）增加「收款信息」分组：收款户名、收款账户、收款码图上传（复用合同附件的上传模式）、缴费说明多行文本。MVP 不显示 `payment_mode` 选择。

### 7.2 PaymentLinkQrModal 扩展

`frontend/src/components/admin/PaymentLinkQrModal.tsx` 在二维码上方增加**支付明细构成**区块（§5.3 版式），数据取自 send-payment-link 响应的 `breakdown`；`has_pending` 为真时显示 §5.5 提醒条。

### 7.3 业主 H5 静态账单页（新增公开页）

新增公开路由 `/pay/:token`（SPA 内，无鉴权、不进侧边栏导航），渲染 PRD §14 的静态账单版式：

```
┌────────────────────────────────┐
│  {payee_name}                  │
│  您好，{owner_name}，房号 {room} │
│  ┌──────────────────────────┐  │
│  │ 应缴合计   ¥ original     │  │
│  │ 已减免    - ¥ waived      │  │
│  │ 应支付     ¥ payable      │  │
│  └──────────────────────────┘  │
│  缴费方式：{payment_instructions}│
│  收款账户：{payee_account}      │
│  收款户名：{payee_name}         │
│  [收款码图 payee_qr]            │
│  ── v1.1 起支持在线支付 ──      │
└────────────────────────────────┘
```

token 过期 / 无效 → 显示「链接已失效，请联系物业重新获取」。

## 8. 测试策略

- **后端**：`compute_payable`（无减免 / 有有效减免 / 减免已过期不计 / 有 pending）；`payment_link` 写入 + token 唯一；`GET /public/payment/{token}`（正常 / 过期 410 / 不存在 404 / 响应不含手机号）；管理端 / 坐席端发送端点跨租户隔离（沿用 `test_payment_link.py`）。
- **前端**：`PaymentLinkQrModal` 渲染明细构成 + has_pending 提醒条；项目编辑页收款字段提交；H5 页按 token 渲染 / 过期态。

## 9. v1.1 展望（不在本方案实现）

公证提存与在线支付：`payment_mode='notary_escrow'`、平台公证提存白名单、微信/支付宝服务商 sub_mch 通道、H5 页「直接付款 / 公证提存付款」按钮、支付回调自动标案件「已缴费」。详见 PRD §14「v1.1：在线支付接入」。

## 10. 待修改 / 新增文件清单

**后端**
- 改 `app/models/case.py`（`Project` 加 5 字段）
- 新建 `app/models/payment_link.py`
- 新建 Alembic 迁移（Project 新字段 + payment_link 表）
- 改 `app/schemas/project.py`（收款字段）、`app/api/admin_projects.py`（创建/更新写入）
- 改 `app/services/payment_link.py`（持久化 + compute_payable + 扩展响应）
- 新建 `app/api/public_payment.py`（`GET /public/payment/{token}`）+ `app/main.py` 注册路由

**前端**
- 改 `src/pages/admin/projects/edit.tsx` + `new.tsx`（收款信息分组）
- 改 `src/components/admin/PaymentLinkQrModal.tsx`（明细构成 + 提醒条）
- 新建 `src/pages/public/PaymentBillPage.tsx` + `src/App.tsx` 公开路由 `/pay/:token`
