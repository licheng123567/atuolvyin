# 服务商督导工作台 Phase 2 — 值班排班 scope-aware 设计文档

> 状态：设计已与用户确认（2026-05-18），待用户复审后转实施计划。
> 前序：Phase 1（9 端点 scope-aware）已实现并合并，见 `2026-05-17-provider-supervisor-workspace-design.md`。

## 背景与目标

Phase 1 把 9 项 `/supervisor/*` 功能改成 scope-aware，但值班排班（`/supervisor/shifts` 系列 4 端点）留到 Phase 2 —— 因为它涉及数据模型迁移。当前 4 端点全部 `require_tenant_roles("supervisor")`（断言 `provider_id IS NULL`），服务商督导无法排班。

**目标**：让服务商督导管理本服务商的值班排班，与物业督导对等但数据 scope 到本服务商。

## 现状调研

- `SupervisorShift` 表：`tenant_id` / `shift_date` / `slot`（morning/afternoon/evening）/ `supervisor_user_id`（FK，可空，**列已存在但代码从未写入，恒为 NULL**）/ `supervisor_name`（文本）。唯一约束 `uq_supervisor_shift_tenant_date_slot` = `(tenant_id, shift_date, slot)`。
- `SupervisorShiftSwapRequest` 表：`tenant_id` / `from_user_id` / `from_user_name` / `to_user_name` / `shift_date` / `slot` / `status`（pending_confirm/accepted/rejected/cancelled）。
- 4 个端点（`app/api/supervisor_shifts.py`）全部 `require_tenant_roles("supervisor")`：
  - `GET /supervisor/shifts` —— 列本周排班 + `is_shift_lead` 标志 + 督导下拉。
  - `POST /supervisor/shifts` —— 排班负责人（`user_account.preferences.is_shift_lead`）批量保存。
  - `POST /supervisor/shifts/swap-request` —— 普通督导对自己班次发起调班申请。
  - `GET /supervisor/shifts/swap-requests` —— 本租户调班申请列表。
- 值班人全程用 `supervisor_name` 文本记录。

## 决策

- **保持名字标识**：值班人继续用 `supervisor_name` 文本，不切 `supervisor_user_id`。名字重复只在同一 scope 内才会冲突（极少），物业侧现状已如此。`supervisor_user_id` 列保持不用。
- **唯一约束方案 A**：弃用旧唯一约束，换成两个 partial unique index —— `WHERE provider_id IS NULL` 的 `(tenant_id, shift_date, slot)` + `WHERE provider_id IS NOT NULL` 的 `(tenant_id, provider_id, shift_date, slot)`。全 PG 版本通用，不依赖 `NULLS NOT DISTINCT`（PG15+）。

## 设计

### ① 数据模型迁移

- `SupervisorShift` 加 `provider_id`：`BigInteger`，FK→`provider.id`（`ondelete="CASCADE"`），可空，带索引。`NULL`=物业侧、非 NULL=服务商侧。
- `SupervisorShiftSwapRequest` 同样加 `provider_id`（同定义）。
- `SupervisorShift` 弃用唯一约束 `uq_supervisor_shift_tenant_date_slot`，换成两个 partial unique index：
  - `uq_supervisor_shift_property` —— `(tenant_id, shift_date, slot)` `WHERE provider_id IS NULL`
  - `uq_supervisor_shift_provider` —— `(tenant_id, provider_id, shift_date, slot)` `WHERE provider_id IS NOT NULL`
- Alembic 迁移：两表各 `ADD COLUMN provider_id`；`SupervisorShift` `DROP CONSTRAINT` 旧唯一约束 + `CREATE` 两个 partial index。既有行 `provider_id` 自动为 NULL（全部物业侧），无需显式回填脚本。`downgrade` 反向。

### ② 4 个端点 scope 改造

`app/api/supervisor_shifts.py` 全部：守卫 `require_tenant_roles("supervisor")` → `require_roles("supervisor")`，注入 `scope: SupervisorScope`（复用 Phase 1 的 `app/api/_supervisor_scope.py` 的 `supervisor_scope` 依赖）。

| 端点 | 改造 |
|------|------|
| `GET /supervisor/shifts` | `_ensure_seed_week` 按 `scope.provider_id` 播种（21 行带 `provider_id`）；周排班查询加 `provider_id` 过滤（物业 `IS NULL`、服务商 `== X`）；督导下拉只列同 scope 的 supervisor（`UserTenantMembership.role='supervisor'` + provider_id 匹配 + `is_active`）。 |
| `POST /supervisor/shifts` | 保存时 upsert 的查询与新建行都带 `provider_id`。 |
| `POST /supervisor/shifts/swap-request` | 新建的 swap request 带 `provider_id`；「只能对自己已排的班次发起调班」校验的 `SupervisorShift` 查询带 `provider_id`。 |
| `GET /supervisor/shifts/swap-requests` | 列表查询加 `provider_id` 过滤。 |

`provider_id` 过滤统一写法：`scope.provider_id is None` → `.where(Model.provider_id.is_(None))`；否则 `.where(Model.provider_id == scope.provider_id)`。可在 `supervisor_shifts.py` 内写一个局部小 helper（如 `_provider_clause(scope, Model)`）复用于 4 端点，避免散落。

`is_shift_lead`（`user_account.preferences.is_shift_lead`）逻辑不变 —— 每个 scope 各自的排班负责人由该用户的 preference 标识，天然按用户隔离，无需 provider 维度。

### ③ 前端

- `frontend/src/config/nav.ts`：`SUPERVISOR_PROVIDER_NAV`「我的工作」区加「值班排班」`/supervisor/shifts`（label/icon 复用 `NAV_CONFIG.supervisor` 既有项）。物业督导 nav 本就含该项，不变。
- 排班页 `frontend/src/pages/supervisor/shifts/index.tsx` scope-agnostic（只调端点、渲染），不改。

## 错误处理

- 沿用项目扁平 `{code, message}`。
- `supervisor_scope()` 解析不到合法 scope → 403 `ERR_NO_SCOPE`，与 Phase 1 一致。
- 既有错误码（`ERR_NOT_SHIFT_LEAD` / `ERR_NOT_OWN_SLOT` / `ERR_VALIDATION` 等）保留。

## 测试

- **多租户隔离（铁律）**：
  - 服务商 A 督导的排班 / 调班申请查不到服务商 B 的、查不到物业侧的。
  - 物业督导查不到任何服务商的排班 / 调班。
  - `_ensure_seed_week` 给服务商 A 播种不影响物业侧、不影响服务商 B。
  - 同 (tenant, date, slot) 下物业排班与服务商 A 排班可并存（partial unique index 验证）。
- 用 testcontainers，自建 fixture，不依赖 seed_demo。
- 前端 `nav.test.ts` 补：`getNavSections("supervisor", "provider:2")` 含 `/supervisor/shifts`（Phase 2 上线后该项才出现）。

## 明确不在范围

- swap-request 的 accept / reject 端点当前根本不存在（物业侧也没有），Phase 2 不补 —— 只把现有 4 端点 scope 化。补全调班审批流是独立需求。
- `supervisor_user_id` 列保持现状（不写入、不读取）。
- 排班页 UI 不改。

## 风险

- partial unique index 的迁移需确保 `DROP` 旧约束与 `CREATE` 新索引顺序正确；迁移后跑一次「物业 + 服务商同槽位并存」的集成测试确认约束行为符合预期。
- `_ensure_seed_week` 是「读时补种」逻辑 —— scope 化后要确认服务商督导首次访问只补种本服务商的 21 行，不会误补物业行。
