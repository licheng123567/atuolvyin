# §9.2 减免归属审批流 + 佣金 — 设计文档

> 来源：`docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` §9「下游影响」第 2 项。
> §9 三项下游需求的最后一个（§9.3 ✅ → §9.1 ✅ → **§9.2**）。

**日期：** 2026-05-16
**分支：** `feat/v2.2-app-ux-fixes`

---

## 1. 问题陈述

角色模型 spec §9.2 拍板了减免（discount / 减免）的 4 条规则，但当前代码：

- `DiscountOffer` 有完整审批流（auto / `pending_supervisor` / `pending_admin` → `approved`/`rejected`/`executed`，7 天过期，`audit_trail`），但**没有 `provider_id`** —— 减免记录完全无服务商归属。
- 减免审批端点 `approve`/`reject`/`escalate` 守卫是 `require_roles(*ALL_ROLES)` —— **服务商侧督导目前能审批减免**，违背「审批权 = 物业」。
- 佣金计算（`admin.py` 内勤、`provider_admin.py` 服务商）是 `Σ amount_owed(stage='paid') × 0.05` —— 用**原始欠款**，完全不扣减免；且佣金率 `0.05` 写死、不可配。

§9.2 本轮把这些落成代码。范围经 brainstorm 确认为 **A + B + C + D1 + D2**（见 §2）。

### 范围

**本轮做（§9.2）：**
- **A. 减免归属** —— `DiscountOffer` 加 `provider_id`。
- **B. 审批流物业侧强制** —— 减免 `approve`/`reject`/`escalate` 改为物业侧专属。
- **C. 佣金不计减免** —— 两处佣金基数改用「实收金额」（扣已执行减免）。
- **D1. 内勤催收员佣金率按项目可配** —— 物业改。
- **D2. 服务商催收员佣金率按项目可配** —— 服务商改。

**明确 OUT of scope（归 §9.2b 另立篇）：**
- **D3. 物业付服务商的服务费率 + 服务费计算** —— 用户已确认服务费率**跟随项目**（届时 §9.2b 在 `Project` 上加一列），且需新建服务费计算逻辑。
- `SettlementStatement.total_amount` 生成 —— 当前无任何生成逻辑，属独立的「服务商结算单生成」功能。

---

## 2. 架构

后端单子项目，无前端 / Android 改动。

- 新增**一条 Alembic 迁移**，加 3 列：`discount_offer.provider_id`、`project.internal_agent_commission_rate`、`project.provider_agent_commission_rate`。
- 新建**一个佣金服务模块 `app/services/commission.py`** —— 收口「实收金额推导」「按项目佣金率解析」全部逻辑；两处佣金端点都调它，杜绝发散。
- 改动落在既有文件：`discount_offers.py`（A + B）、`admin.py`（C + D1 计算）、`provider_admin.py`（C + D2 计算 + D2 写端点）、`admin_projects.py` / schema（D1 写）、相关 schema。

---

## 3. Part A — 减免归属

### 3.1 模型
`DiscountOffer`（`app/models/discount_offer.py`）新增：

```
provider_id: int | None  FK → service_provider.id  ON DELETE SET NULL  可空
```

`NULL` = 物业内勤发起的减免；非 `NULL` = 服务商催收员发起，值为其服务商 id。无 CHECK 约束（纯可空 FK）。

### 3.2 创建时写入
`discount_offers.py` 的 `create_offer`（`POST /cases/{case_id}/discount-offers`）—— 构造 `DiscountOffer` 行时增加 `provider_id=payload.get("provider_id")`。物业内勤的 token 无 `provider_id`（None），服务商催收员的 token 带 `provider_id`。零额外查询。

### 3.3 透出
`DiscountOfferOut` schema（`app/schemas/discount.py`）增加 `provider_id: int | None = None`。

---

## 4. Part B — 审批流物业侧强制

「审批权 = 物业」结构性落地：减免的**审批 / 拒绝 / 升级**只能物业侧操作。

`discount_offers.py` 三个端点的守卫从 `require_roles(*ALL_ROLES)` 改为
`require_tenant_roles("supervisor", "admin", "superadmin")`：

| 端点 | 旧守卫 | 新守卫 |
|------|--------|--------|
| `POST /discount-offers/{id}/approve` | `require_roles(*ALL_ROLES)` | `require_tenant_roles("supervisor","admin","superadmin")` |
| `POST /discount-offers/{id}/reject` | `require_roles(*ALL_ROLES)` | `require_tenant_roles("supervisor","admin","superadmin")` |
| `POST /discount-offers/{id}/escalate` | `require_roles(*ALL_ROLES)` | `require_tenant_roles("supervisor","admin","superadmin")` |

- `require_tenant_roles` 断言 `provider_id IS NULL` —— 服务商侧用户（即便角色名是 supervisor）一律 403。
- 端点内部按 `offer.status` 与 `approver_role_required` 的分层校验（`pending_supervisor` 须 supervisor、`pending_admin` 须 admin、escalate 须 supervisor）**保留不动** —— 仅外层守卫收紧。

**不动的端点**：`create`（服务商催收员仍可发起减免）、`list` / `detail`（双方可查）、`mark-executed`（记录业主已缴清）。

**「物业预先授权的额度」** = 既有项目级减免阈值（`Project.discount_*_threshold_pct` / `late_fee_waive_*`）。服务商催收员发起的减免，落在 auto 阈值内 → 自动通过（物业已通过项目策略预授权该档）；超阈值 → 进 `pending_supervisor` / `pending_admin`，由物业侧审批。**不新增按服务商的额度列。**

---

## 5. Part C — 佣金不计减免

### 5.1 实收金额推导
`app/services/commission.py` 新增：

```python
def executed_discount_amounts(db: Session, case_ids: list[int]) -> dict[int, Decimal]:
    """case_id → 业主实收额，仅含有 status='executed' 减免的案件。

    §9.2-C：减免部分不计佣金 —— 已执行减免的案件，实收 = 该减免的 proposed_amount
    （业主实际缴的钱）。无已执行减免的案件不在返回 dict 内，调用方回退 amount_owed。
    多条 executed（罕见）→ 按 id 取最新一条。
    """
```

实现要点：`select(DiscountOffer.case_id, DiscountOffer.proposed_amount).where(case_id IN (...), status == 'executed').order_by(DiscountOffer.id)`，结果入 dict（同 case_id 后值覆盖 → 最新 id 胜出）。空 `case_ids` 直接返回 `{}`。

调用方对每个已付案件：`collected = executed.get(case_id) or (amount_owed or 0)`。

**不动 `CollectionCase`、不加收款表** —— `DiscountOffer` 记录本身是实收的权威来源，on-the-fly 推导。

### 5.2 佣金率解析
`app/services/commission.py` 还新增：

```python
DEFAULT_COMMISSION_RATE = Decimal("0.05")

def internal_agent_rate(project: Project | None) -> Decimal:
    """§9.2-D1：项目级内勤佣金率；NULL / 无项目 → 系统默认 0.05。"""

def provider_agent_rate(project: Project | None) -> Decimal:
    """§9.2-D2：项目级服务商催收员佣金率；NULL / 无项目 → 系统默认 0.05。"""
```

---

## 6. Part D1 / D2 — 佣金率按项目可配

### 6.1 模型
`Project`（`app/models/case.py`）新增两列：

| 列 | 类型 | 说明 |
|----|------|------|
| `internal_agent_commission_rate` | `Numeric(6,4)` 可空 | D1：物业内勤催收员佣金率（如 `0.0500`）；NULL → 系统默认 |
| `provider_agent_commission_rate` | `Numeric(6,4)` 可空 | D2：服务商催收员佣金率；NULL → 系统默认 |

不加 `TenantSettings` 默认列（YAGNI —— 按项目 + 系统默认 `0.05` 够用；租户级默认列留作后续）。

### 6.2 D1 写入 —— 物业侧
- `internal_agent_commission_rate` 加进 `ProjectCreateIn` 与 `ProjectUpdateIn` schema（`app/schemas/project.py`），`Field(None, ge=0, le=1)`。
- 复用既有 `PATCH /api/v1/admin/projects/{id}`（`require_tenant_roles(*ADMIN_ROLES)`）—— 其 `setattr` 流程自动覆盖新字段，无需改端点逻辑。
- `POST /api/v1/admin/projects`（创建）同理经 `ProjectCreateIn` 接收。

### 6.3 D2 写入 —— 服务商侧
- **不**进 `ProjectUpdateIn` —— 物业 PATCH 碰不到 D2。
- 新增端点 `PATCH /api/v1/provider/projects/{project_id}/commission-rate`，守卫 `require_provider_roles("project_manager", "admin")`：
  - Body：`{"provider_agent_commission_rate": Decimal}`（`Field(ge=0, le=1)`）。
  - 作用域：`project.provider_id` 须等于 token 的 `provider_id`，否则 `404`。
  - 与既有 `PATCH /provider/projects/{id}/pm` 同分面、同风格。

### 6.4 透出
`ProjectOut` schema 增加 `internal_agent_commission_rate` 与 `provider_agent_commission_rate`（均 `Decimal | None`）—— 双方都可见两个率，各自只能改自己那个。

---

## 7. 两处佣金计算改造

两处都从「Σ base 后乘单一率」改为「逐案件 `实收 × 该案项目佣金率`，再求和」。

### 7.1 内勤 —— `admin.py` `GET /admin/agent-commissions`
- 每个 agent 的已付案件查询补选 `CollectionCase.id` 与 `CollectionCase.project_id`（原仅选 `amount_owed`）。
- 批量取这些案件的 `executed_discount_amounts` 与所属 `Project`（按 `project_id` 批量 `select`，避免 N+1）。
- 逐案件：`collected = executed.get(case_id) or amount_owed`；`rate = internal_agent_rate(project)`；`case_commission = (collected * rate).quantize(0.01)`。
- 每个 agent：`base = Σ collected`，`commission = Σ case_commission`。
- `AgentCommissionList.total_base` / `total_commission` 相应为各 agent 之和。`AgentCommissionItem` 形状不变（数值按新口径算）。

### 7.2 服务商 —— `provider_admin.py` `GET /provider/team/{member_user_id}/commission`
- 已付案件查询补 `project_id`（已选 `CollectionCase` 实体，含 `id`/`project_id`）。
- 同样批量取 `executed_discount_amounts` + 批量取 `Project`。
- 逐案件构造 `CommissionLineItem`：`paid_amount` = 实收额（`collected`）；新增字段 `commission_rate`（= 该案 `provider_agent_rate(project)`）。
- `ProviderMemberCommission`：`base_amount = Σ collected`；`commission = Σ (collected × rate).quantize(0.01)`；`commission_rate` 改为**加权有效率** = `commission / base_amount`（`base_amount` 为 0 时取 `0`）。

`CommissionLineItem` schema（`app/schemas/provider_admin.py`）新增 `commission_rate: Decimal`。

---

## 8. 数据模型与迁移

新增一条迁移 `24018_v220_discount_provider_commission_rates.py`，`revision="24018v220d"`，`down_revision="24017v220c"`（当前 head）：

- `discount_offer` 加 `provider_id BIGINT NULL` + FK→`service_provider.id` `ON DELETE SET NULL`。
- `project` 加 `internal_agent_commission_rate NUMERIC(6,4) NULL`。
- `project` 加 `provider_agent_commission_rate NUMERIC(6,4) NULL`。
- `downgrade()` 反向 drop 三列，完整可逆。

ORM 模型（`DiscountOffer`、`Project`）与迁移保持一致。无 CHECK 约束（纯可空列）。

---

## 9. 安全影响

- **Part B 是收紧权限**：减免审批从「任意角色（含服务商督导）」收紧为「物业侧 supervisor/admin/superadmin」。无放宽面。
- Part A 的 `provider_id` 为减免提供归属溯源，服务于结算分析与「过度减免」风控归因。
- Part C 修正佣金口径：服务商 / 内勤都不再对「已减免掉的金额」抽佣 —— 消除「过度减免快速成单」的利益冲突。
- D2 写端点用 `require_provider_roles` + `project.provider_id` 作用域校验 —— 服务商 A 改不了服务商 B 的项目佣金率（`404`）。
- D1 写仍走物业 admin 端点；物业改不了 D2（D2 不在 `ProjectUpdateIn`）。
- 多租户：所有查询带 `tenant_id`；佣金计算的案件查询本就按 `tenant_id` 过滤。

---

## 10. 测试

DB 集成测试用 testcontainers-postgres，禁止 mock 数据库。

**Part A：**
- 服务商催收员发起减免 → `DiscountOffer.provider_id` = 其 provider_id。
- 物业内勤发起减免 → `provider_id` 为 `NULL`。
- `DiscountOfferOut` 透出 `provider_id`。

**Part B：**
- 物业 supervisor/admin 审批/拒绝/升级减免 → 放行。
- 服务商侧 supervisor（`provider_id` 非空）调 approve/reject/escalate → `403`。
- 端点内部分层校验仍生效（`pending_supervisor` 非 supervisor → 拒）。

**Part C：**
- `executed_discount_amounts`：有 executed 减免的案件返回 `proposed_amount`；无的不在 dict；多条取最新。
- 案件有已执行减免时，佣金基数 = 减免后实收额，不是原始 `amount_owed`。

**Part D1/D2：**
- `internal_agent_rate` / `provider_agent_rate`：项目有率取项目率，NULL / 无项目取 `0.05`。
- 物业 `PATCH /admin/projects/{id}` 设 `internal_agent_commission_rate` → 落库。
- 服务商 `PATCH /provider/projects/{id}/commission-rate` 设 `provider_agent_commission_rate` → 落库。
- 服务商 A 改服务商 B 的项目佣金率 → `404`。
- 非服务商侧 / 非 PM/admin 调 D2 端点 → `403`。

**佣金计算：**
- 内勤佣金：跨两个项目（不同内勤率）的已付案件 → 逐案按各自项目率计算后求和。
- 服务商佣金：`CommissionLineItem.paid_amount` 为实收额、带 `commission_rate`；`ProviderMemberCommission.commission` 为逐案之和、`commission_rate` 为加权有效率。
- 减免 + 项目率组合：一个已付案件既有已执行减免、其项目又有非默认率 → 佣金 = `proposed_amount × 项目率`。

---

## 11. 文件清单

| 文件 | 操作 |
|------|------|
| `poc/backend/app/models/discount_offer.py` | 改：`DiscountOffer` 加 `provider_id` |
| `poc/backend/app/models/case.py` | 改：`Project` 加 2 个佣金率列 |
| `poc/backend/alembic/versions/24018_v220_discount_provider_commission_rates.py` | 建：3 列迁移 |
| `poc/backend/app/services/commission.py` | 建：`executed_discount_amounts` + `internal_agent_rate` + `provider_agent_rate` + `DEFAULT_COMMISSION_RATE` |
| `poc/backend/app/api/discount_offers.py` | 改：create 写 `provider_id`；approve/reject/escalate 守卫收紧 |
| `poc/backend/app/schemas/discount.py` | 改：`DiscountOfferOut` 加 `provider_id` |
| `poc/backend/app/api/admin.py` | 改：`agent-commissions` 逐案按项目率 + 扣减免 |
| `poc/backend/app/api/provider_admin.py` | 改：`team/{id}/commission` 逐案计算；新增 D2 写端点 |
| `poc/backend/app/schemas/project.py` | 改：`ProjectCreateIn`/`ProjectUpdateIn`/`ProjectOut` 加佣金率字段 |
| `poc/backend/app/schemas/provider_admin.py` | 改：`CommissionLineItem` 加 `commission_rate` |
| `poc/backend/tests/...` | 建/改：§10 全部测试用例 |
| `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` | 改：§9.2 标注已实现 |

无前端 / Android 改动（本期只交付后端能力）。
