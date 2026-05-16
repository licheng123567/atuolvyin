# 设计:角色模型重构(方案 ① 大爆炸单分支)

> 日期:2026-05-16
> 分支:`feature/role-model-refactor`
> 状态:设计已确认,待写实现计划

## 1. 背景与动机

### 1.1 起因

补全服务商(ServiceProvider)侧组织结构时发现:当前 11 个角色把「组织归属」硬编进了角色名,导致模型不对称且无法支撑外包催收的真实业务。

具体问题:

- `project_manager_property` 与 `project_manager_provider` 是**同一职能(项目经理)**被拆成两个角色;而 `supervisor` / `agent` 又没有 `_provider` 变体 —— 服务商无法拥有自己的督导。
- 外包催收场景下真正打电话的是**服务商的催收员**,其通话的一线质检责任在服务商。当前模型无法表达「服务商督导」。
- seed 里 `agent_external`(外勤小王)的 membership 直接挂在物业租户下、**不带 `provider_id`**,实为「物业自有外勤」,不是服务商催收员 —— 缺真正的服务商催收员账号。
- `provider_admin` / `project_manager_provider` 登录返回的 `scope` 是 `tenant:3` 而非 `provider:{id}`,违反 `CLAUDE.md`「服务商数据通过 `scope = provider:{id}` 隔离」的规则 —— 服务商隔离链路未打通。
- 现状本身已存在命名不一致:`platform_super`(23 处)与 `platform_superadmin`(43 处)并存;`property_manager_*` 与 `project_manager_*` 并存。
- 冗余字段:`UserTenantMembership.source_type`(`INTERNAL`/`PROVIDER`)与 `provider_id IS NULL` 携带完全相同的信息 —— 同一个「物业侧 vs 服务商侧」bit 在库里有两种表示。
- 安全隐患:`auth.py` 在「用户无任何 membership」时把 `role` 默认落成 `platform_superadmin` —— 任意无 membership 的账号都会变成超管。

### 1.2 现状摘要

- `UserTenantMembership.role` 是 free-text `Text` 列,**无 DB enum / CHECK 约束**。
- 角色字符串以字面量散落在 ~25 个后端文件、~10 个前端文件、2 个 Android 文件。
- 项目阶段:D→E 过渡(MVP 编码),纯 dev 环境,唯一数据是 seed,无 prod、无真实用户。

## 2. 目标

把「角色」从一维字符串拆成**三个正交维度**,角色枚举收敛为纯职能角色,并加 DB CHECK 约束从源头防非法值。

成功标准:

- 角色从 11 个(9 组织角色 + 2 平台角色)收敛为 6 个组织职能角色(`membership.role`)+ 2 个平台角色(`account.platform_role`)。
- 服务商可拥有完整组织结构(管理员 / 项目经理 / 督导 / 催收员 / 法务 / 工单),均通过 `provider_id` 维度表达,**零新增角色名**。
- 服务商数据隔离 `scope=provider:{id}` 链路打通。
- 「无 membership 即超管」安全隐患消除。
- 三端(后端 / PC 前端 / Android)角色字面量统一到单一事实源。
- `api_smoke.py` 全角色冒烟通过;覆盖率守住 `CLAUDE.md` 要求(P0 ≥ 80%,关键路径 ≥ 90%)。

## 3. 范围

| 范围内 | 范围外 |
|--------|--------|
| 后端 role 枚举收敛 + 鉴权层改造 + DB 迁移 | 减免额度机制 / 减免审批流 / 佣金算法 |
| PC 前端 role 判断 / 路由 / 菜单 | 服务商法务的法务转化业务流 |
| Android role 字面量(`Api.kt`、`AudioStreamClient.kt`) | PRD 正式章节落地(后续走 `prd-section-writer`) |
| DB CHECK 约束(`role` / `platform_role` / `work_mode`) | |
| 删除冗余列 `UserTenantMembership.source_type` | |
| seed 改写 + 补服务商催收员 / 服务商督导账号 | |
| 测试 + 相关文档同步 | |

## 4. 目标数据模型

三个正交维度:

| 维度 | 落点 | 取值 |
|------|------|------|
| 平台身份 | `UserAccount.platform_role`(**新列**) | `superadmin` / `ops` / `NULL` |
| 组织职能 | `UserTenantMembership.role`(**改值域**) | `admin` / `project_manager` / `supervisor` / `agent` / `legal` / `coordinator` |
| 组织归属 | `UserTenantMembership.provider_id`(已存在) | `NULL`=物业侧 / `X`=服务商 X 侧 |
| 工作方式 | `UserTenantMembership.work_mode`(**新列**) | `internal` / `external`(仅 `agent`,其余 `NULL`) |

### 4.1 DB CHECK 约束(三条)

- `ck_membership_role`: `role IN ('admin','project_manager','supervisor','agent','legal','coordinator')`
- `ck_account_platform_role`: `platform_role IS NULL OR platform_role IN ('superadmin','ops')`
- `ck_membership_work_mode`: `(role = 'agent') = (work_mode IS NOT NULL)` —— work_mode 非空当且仅当角色为 `agent`

> 决策:用 CHECK 约束而非 Postgres 原生 ENUM 类型。CHECK 可随时 `DROP/ADD`;原生 ENUM 的 `ALTER TYPE` 单向、删值极难,角色集未来仍可能演进。

### 4.2 衍生组合(零新增角色名即可表达)

- 服务商管理员 = `admin` + `provider_id` 非空
- 服务商项目经理 = `project_manager` + `provider_id` 非空
- 服务商督导 = `supervisor` + `provider_id` 非空
- 服务商催收员 = `agent` + `provider_id` 非空 + `work_mode`
- 服务商法务 = `legal` + `provider_id` 非空
- 服务商工单 = `coordinator` + `provider_id` 非空

## 5. 数据迁移(一条 alembic + 改 seed)

### 5.1 旧值 → 新值映射

| 旧 role | 新 role | provider_id | work_mode | platform_role |
|---------|---------|-------------|-----------|---------------|
| `admin` | `admin` | 不变 | `NULL` | — |
| `provider_admin` | `admin` | 不变(非空) | `NULL` | — |
| `supervisor` | `supervisor` | 不变 | `NULL` | — |
| `agent_internal` | `agent` | 不变 | `internal` | — |
| `agent_external` | `agent` | 不变 | `external` | — |
| `legal` | `legal` | 不变 | `NULL` | — |
| `coordinator` | `coordinator` | 不变 | `NULL` | — |
| `project_manager_property` / `property_manager_property` | `project_manager` | 不变 | `NULL` | — |
| `project_manager_provider` / `property_manager_provider` | `project_manager` | 不变(非空) | `NULL` | — |
| `platform_ops` membership | **删除该 membership 行** | — | — | 账号 `platform_role='ops'` |
| 无 membership 的超管账号 | — | — | — | 账号 `platform_role='superadmin'` |

> 注:`work_mode` 区分由旧角色名携带 —— `agent_internal`→`internal`、`agent_external`→`external`。

### 5.2 迁移步骤(`upgrade()`)

1. 加列 `user_account.platform_role`、`user_tenant_membership.work_mode`(均可空)。
2. UPDATE 回填 `role` / `work_mode`(按 5.1 映射)。
2b. 删除冗余列 `user_tenant_membership.source_type`(与 `provider_id IS NULL` 同义)。
3. 处理平台角色:
   - 持有 `platform_ops` membership 的账号 → 回填 `platform_role='ops'` 并删除该 membership 行。
   - 持有 `platform_superadmin` / `platform_super` membership 的账号(若有)→ 回填 `platform_role='superadmin'` 并删除该 membership 行。
   - 当前**无任何 membership** 的账号 → 回填 `platform_role='superadmin'`。这是一次性数据修复(迁移后此推断规则即废止);dev seed 中仅 `13000000000` 一个此类账号。迁移脚本须打印受影响账号清单,若出现非预期的游离账号需人工确认。
4. 加三条 CHECK 约束(4.1)。

`downgrade()`:反向 —— 删 CHECK → 重建 `platform_ops` membership → 重建 `source_type` 列并按 `provider_id` 回填 → role 反映射 → 删两个新列。完整可逆。

`source_type` 的 5 处写入点(`admin.py` ×4、`provider_admin.py` ×1)与 seed 文件中的写入随重构一并清理。

### 5.3 seed 改写

`scripts/seed_demo.py` 同步改为新值域,并**补两个真账号**:

- 服务商催收员:`agent` + `provider_id=provider.id` + `work_mode='external'`
- 服务商督导:`supervisor` + `provider_id=provider.id`

## 6. 鉴权层改造

- **登录角色解析**(`app/api/auth.py`):先看 `account.platform_role` —— 命中则 `role=superadmin/ops`、`scope=platform`;否则取 membership 的 `role`。
- **`scope` 修正**:membership 的 `provider_id` 非空 → `scope=provider:{provider_id}`(修掉当前 `provider_admin` 错返 `tenant:3` 的 bug);否则 `scope=tenant:{tenant_id}`。scope 取值域:`platform` / `tenant:{id}` / `provider:{id}`。
- **`app/core/phone_visibility.py` 重写**:`INTERNAL_ROLES` / `PROVIDER_ROLES` 等按角色名分类的 frozenset 删除,改为按 `provider_id IS NULL` 判断内部 / 服务商归属。
- **`require_roles(...)`** 调用点全部按新 6 角色更新;凡涉及「物业侧 vs 服务商侧」的判断改用 `provider_id`。
- **超管隐患修复**:`auth.py` 不再在「无 membership」时默认超管;超管必须显式持有 `platform_role='superadmin'`。

### 6.1 越权守卫 —— `require_tenant_roles` / `require_provider_roles`(执行期发现)

角色折叠(`provider_admin→admin`、`project_manager_provider/_property→project_manager`)使「物业侧 vs 服务商侧」不再由角色名携带。重构前 `admin_*.py` 等物业专用端点的 `require_roles("admin")` 天然排斥服务商(`provider_admin` 不在元组里);折叠后服务商 admin 的 `role` 变成 `admin`,会**误获整族物业管理端点的访问权** —— 系统性越权。

修复:在 `app/core/security.py` 新增两个依赖:

- `require_tenant_roles(*roles)` = `require_roles(*roles)` + 断言 `payload["provider_id"] is None`(仅物业侧)
- `require_provider_roles(*roles)` = `require_roles(*roles)` + 断言 `payload["provider_id"] is not None`(仅服务商侧)

判定规则(机械、可对 git 核验,**不改变行为**):逐个端点比对重构前 `require_roles` 元组 —— 元组**不含** `provider_admin`/`project_manager_provider` 的端点是物业专用,改用 `require_tenant_roles`;原本服务商专用的改用 `require_provider_roles`;两侧皆可的保持 `require_roles`。目标是**精确还原重构前的访问范围**。

## 7. 三端字面量替换

| 端 | 范围 | 量级 |
|----|------|------|
| 后端 | ~25 个 `app/api/*.py` + `schemas` + `workers` 内 role 字符串,统一到**新增单一事实源 `app/core/roles.py`**(角色常量 + 校验集合) | 中 |
| PC 前端 | role 判断、`RoleHomeRedirect`、菜单 `nav.ts`、路由守卫,统一到 `types/index.ts` 的 `UserRole` | 中 |
| Android | `Api.kt`(`agent_internal`)、`AudioStreamClient.kt`(`supervisor` WS 路径) | 小 |

后端新增 `app/core/roles.py` 后,禁止任何文件再散落 role 字面量。

## 8. 测试与文档

- 后端:`scripts/api_smoke.py`、`tests/` 内 role fixture、`conftest.py` 更新;**新增**迁移正确性测试(回填映射逐条断言)+ CHECK 约束拒绝非法值测试。
- 前端:Vitest / Playwright 内 role mock 更新。
- Android:`*Test.kt` 内 role 常量更新。
- 文档同步:`docs/account-architecture.md`、`docs/E2E_SMOKE.md` 角色矩阵、`CLAUDE.md` 多租户规则节。
- 覆盖率:守住 `CLAUDE.md` 要求(P0 ≥ 80%,拨打/上传/ASR/计费关键路径 ≥ 90%)。

## 9. 下游影响(本次只记录,不实现)

以下业务规则在本次重构中已拍板,但**不在实现范围内** —— 建议后续走 `prd-section-writer` 正式落进 PRD:

### 9.1 服务商法务

- 模型:`legal` + `provider_id` 非空即可表达,零新增。
- 职责边界:服务商法务职责限于**整理催收材料、发起法务转化请求**(对应 `legal_conversion_requests` 流)、跟进进度。
- 物业费债权人是物业公司,**诉讼主体与终审决定权始终在物业法务 / 物业委托的律所**(`LawFirm` 实体)。
- 服务商法务**可选** —— 小服务商无法务时,催收员直接发起法务转化请求给物业法务。seed 不强制造此账号。
- 概念区分:「服务商法务(角色)」与「法务类服务商 / 律所(组织实体,`ServiceProvider.provider_type='legal'` 或 `LawFirm`)」是两回事,不可混淆。

### 9.2 减免归属

- **财务归属 = 物业**:减免减的是业主欠物业的钱,即物业的应收账款。
- **审批权 = 物业**:服务商催收员只能在物业**预先授权的减免额度 / 规则**内提减免;超额必须走物业(`admin` / 物业 `project_manager`)审批。
- **来源标记 = `provider_id`**:减免记录带上发起人的 `provider_id`,用于结算分析与风控归因 —— 这正是角色模型必须打通 `provider_id` 的业务理由之一。
- **结算风控**:服务商按回收金额抽佣会诱发「过度减免快速成单」的利益冲突;故佣金基数按**实收金额**算,**减免部分不计佣金**;减免授权额度是必须的风控闸门。
- 减免额度机制、审批流、佣金算法均为后续独立需求。

### 9.3 WS 广播业主电话脱敏(重构暴露的遗留项)

- 现象:`SupervisorManager.broadcast` 按 `tenant_id` 群发,`calls_v1.py` 的实时通话事件广播对 `supervisor` 固定 `provider_id=None`、统一明文。
- 旧模型下 `supervisor` 必是物业内部,行为正确;新模型允许服务商侧督导(`supervisor` + `provider_id`),其连入同一 tenant 房间会收到明文业主电话 —— 是过度披露。
- 根治需在 `broadcast` 内按每个订阅连接的 `provider_id` 逐一脱敏(架构改动)。本次重构不做,代码已留 `TODO(v2.2-followup)`,作为后续独立需求记录。

## 10. 风险与回滚

- **风险**:单分支大爆炸,主要风险是「漏改某处 role 字面量」。缓解 = 后端单一常量源 `app/core/roles.py` + grep 全量核对 + `api_smoke.py` 全角色冒烟。
- **JWT 旧 token 失效**:用户重新登录即可(dev 无 prod,可接受)。
- **回滚**:`alembic downgrade -1` + `git revert`;迁移 `downgrade()` 完整可逆。
- **有序 commit**:迁移 → 后端常量源 → 后端调用点 → 前端 → Android → seed/测试/文档。

## 11. 已确认决策清单

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 重构范围 | 全三端(后端 + PC + Android)+ DB CHECK 约束 |
| 2 | 内勤/外勤建模 | 合并为 `agent` + `work_mode` 字段 |
| 3 | 平台角色建模 | `UserAccount.platform_role` 字段 |
| 4 | 执行策略 | 方案 ① 大爆炸单分支 |
| 5 | DB 约束形式 | CHECK 约束(非 Postgres 原生 ENUM) |
| 6 | 服务商法务 | 允许(`legal`+`provider_id`),职责受限,seed 不强制 |
| 7 | 减免归属 | 财务归属 + 审批权在物业,限额内可提,记录带 `provider_id` |
| 8 | 冗余字段 `source_type` | 一并删除,组织归属统一由 `provider_id IS NULL` 判断 |
