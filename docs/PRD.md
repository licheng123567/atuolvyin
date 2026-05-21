# 有证慧催 — 催收辅助 AI 系统 PRD

**版本**：v0.7
**日期**：2026-04-28
**状态**：评审中

---

## 1. 产品概述

**有证慧催**是一款面向物业管理公司的 AI 辅助催收系统。核心卖点是**实时通话 AI 辅助**：外呼员通话中 AI 即时识别业主异议并推送话术建议，延迟 ≤ 3 秒；同时支持通话录音事后批量分析。配合 CRM 公海/私海管理机制，帮助物业公司系统化管理催收全流程，提升回款率。

**核心价值**：让每个外呼员在每通电话中都有 AI"副驾"，让管理层无需听录音即可实时掌握催收进度与团队表现。

---

## 2. 产品定位

| 维度 | 说明 |
|------|------|
| 目标客户 | 中大型物业管理公司（管理 500 户以上） |
| 核心场景 | 物业费催收 |
| 平台 | PC 端（管理/督导）+ Android App（外呼员） |
| 核心卖点 | **实时 AI 话术辅助**（通话中即时显示建议，延迟 ≤ 3 秒） |
| 差异化 | 录音上传分析 + 实时辅助双模式，多租户 CRM 公海/私海自动流转 |
| 商业模式 | SaaS 订阅（主）+ 服务商结算抽佣 + 合规存证增值服务 + 法务转化通道 |
| 长期愿景 | 物业催收行业中台：从工具→撮合市场→行业数据平台→垂直法律服务 |
| 技术栈 | **Refine.dev + shadcn/ui**（PC CRM 框架）/ Kotlin Android（App）/ FastAPI + PostgreSQL + Redis（后端）/ **n8n**（流程自动化）|

### 2.1 技术选型说明

#### PC 端：Refine.dev + shadcn/ui（替代从零构建 CRM UI）

系统 PC 端本质是一套数据密集型 CRM 管理后台，[Refine.dev](https://refine.dev) 是专为此场景设计的开源 React 框架：

| 能力 | Refine 提供 | 节省工作量 |
|------|-----------|----------|
| CRUD 数据绑定 | `useList / useShow / useCreate / useUpdate` 钩子，直连 FastAPI REST | 省去手写所有数据请求逻辑 |
| 表格、表单、时间线 | 与 shadcn/ui 原生集成，开箱即用 | 省去 CRM 组件开发 |
| 权限控制 | `accessControlProvider` 接口，接入我们的角色体系 | 省去前端权限层 |
| 实时订阅 | `useSubscription`，对接 FastAPI WebSocket | 省去手写 WebSocket 状态管理 |
| 多租户 UI | 路由隔离 + `useGetIdentity` 携带 tenant_id | 省去多租户 UI 逻辑 |

**使用方式**：FastAPI 后端完全不动，Refine 作为 PC 前端框架消费 `/api/v1/*` REST 接口。与原规划的 shadcn/ui 完全兼容，Refine 使用 shadcn/ui 作为组件库，不冲突。

**预计节省开发量**：PC 端 CRM 基础功能（表格/详情/时间线/权限）从 8 周压缩到 3-4 周。

#### 流程自动化：n8n（替代自建 Celery CRM 路由规则）

CRM 公海/私海流转规则、定时结算任务、承诺付款提醒等**业务规则**适合用 [n8n](https://n8n.io)（开源可视化工作流引擎）来管理：

```
FastAPI 记录 call_log / 案件状态变更
    ↓ 触发 Webhook
n8n 工作流
    ├── 判断案件是否超时 → 回公海
    ├── 判断承诺日期到期 → 生成提醒通知
    ├── 月末触发 → 生成结算单草稿
    └── 联系频次达上限 → 锁定拨打按钮
```

- **优势**：催收规则调整无需改代码，产品经理/运营直接在 n8n UI 修改工作流
- **部署**：n8n 自托管（Docker），与 FastAPI 通过 Webhook/REST API 通信
- **MVP 阶段**：规则简单时仍用 Celery；v1.1 引入 n8n 接管复杂流程规则

#### 后端 AI 层：保持 FastAPI（不替换）

ASR（DashScope）+ LLM（Qwen-Plus）+ WebSocket 实时推流是系统核心竞争力所在，保留在 FastAPI 自建逻辑中，不用任何第三方框架替换。

---

## 3. 多租户与服务商架构

### 3.1 三层主体结构

```
有证慧催 SaaS 平台
├── 平台超管（运营团队）
│     管理所有租户和服务商，查看全局运营与收入数据
│
├── 租户（物业公司）—— 数据拥有者
│     ├── XX 物业（独立 schema，独立存储）
│     ├── YY 物业
│     └── ZZ 物业（各自完全隔离）
│
└── 服务商（ServiceProvider）—— 独立注册主体
      ├── 兴华律所（类型：法务）
      │     签约：XX物业、YY物业
      │     成员：律师王某、律师李某
      └── 聚英兼职团队（类型：催收）
            签约：XX物业、YY物业、ZZ物业
            成员：催收员张某、催收员陈某
```

### 3.2 账号结构：一人一账号，多租户挂靠

```sql
User            -- 全局唯一账号（一人一个）
UserTenantMembership  -- 用户↔租户多对多 + 同一租户内多角色
  ├── user_id
  ├── tenant_id
  ├── source_type    -- INTERNAL（直招）/ PROVIDER（服务商派遣）
  ├── provider_id    -- 来自哪个服务商
  ├── role           -- 在该租户的角色
  ├── quota          -- 认领上限（每租户独立）
  ├── expire_at      -- 合约到期日
  └── access_hours   -- 可访问时段
```

**v1.6.9 — 同租户内多角色（multi-membership 同租户）**：一个 User 在同一 tenant 下可同时拥有多个 role 行（如督导小李同时是 `supervisor` + `agent_internal`）。Topbar 右上角显示「可切换 N 个角色」下拉，点击调 `POST /auth/select-membership` 颁发新 token，前端 `queryClient.clear()` 后硬刷新到 `/`。

**业务约束**（避免数据查询多结果异常）：所有按 `user_id` 查 membership 的 SQL **必须**附加 `role` 过滤或 `limit(1)`，特别是 `assigned_to` 字段对应的角色查找（应显式 `role IN ('agent_internal','agent_external')`）。

### 3.3 多租户登录体验

```
登录后：
  只属于 1 个租户  →  直接进入工作台
  属于 2+ 个租户  →  显示工作空间选择页

┌──────────────────────────────────────────┐
│  你好，张明！选择今天要工作的空间          │
│                                          │
│  ┌──────────────┐  ┌──────────────┐     │
│  │  XX 物业      │  │  YY 物业      │     │
│  │  待处理 12件  │  │  待处理  8件  │     │
│  └──────────────┘  └──────────────┘     │
│                                          │
│  [合并视图 — 查看所有公司的任务]          │
└──────────────────────────────────────────┘

合并视图：统一列表，每条案件带公司角标
  [XX物业] 张三  5-203  ¥3,200  跟进中
  [YY物业] 李四  2-101  ¥8,500  待联系
  右上角 [全部公司 ▼] 可快速切换单一公司视图
```

### 3.4 数据隔离原则

| 规则 | 说明 |
|------|------|
| 案件数据隔离 | 服务商成员只能看到该租户分配给自己的案件 |
| 跨租户不透明 | XX物业看不到"这个律师也在给YY物业服务" |
| 绩效独立统计 | 每个租户独立统计该成员的绩效，不跨租户合并 |
| 结算独立核算 | 每个服务商与每个租户的结算单独生成，互不可见 |

### 3.5 服务商签约流程

```
物业公司管理员 → 合作伙伴 → 邀请服务商
    ↓ 输入服务商名称/联系人，系统生成邀请码
服务商注册/登录 → 接受邀请
    ↓ 服务商管理员选择派遣哪些成员
物业公司管理员确认 → 设置角色/配额/到期日/结算标准
    ↓ 成员账号自动获得该租户访问权限
```

- 所有 API 强制携带 `tenant_id`，中间件层校验，禁止跨租户访问
- MVP 阶段服务单一租户，v1.1 启用完整多租户 + 服务商体系

#### 3.5.1 服务商数据可见性边界(v0.7.0 锁定)

**核心约束**:服务商对案件 / 通话 / 业主等业务数据的可见性由 `project.provider_id` 决定,**不走 `ProviderTenantContract` 表**。这是 v0.7.0 Wave C 调研确认的现状。

```
服务商可见案件集合 SQL:
SELECT cc.* FROM collection_case cc
JOIN project p ON cc.project_id = p.id
WHERE p.provider_id = :self_provider_id
```

**为什么不走 Contract**:`ProviderTenantContract` 管签约关系(谁和谁签约 / 服务期 / 结算周期),但**具体可见的案件**由「物业 admin 创建项目时把 `Project.provider_id` 设给该服务商」决定。一个签约关系下,物业可能有多个项目,只把其中 N 个外包给该服务商。

**督导/法务/PM/催收员的 scope 实现**(都用 `_supervisor_scope.py` 同款模式):
- 物业侧(scope=tenant):看本租户内 + **非服务商接案**(`project.provider_id IS NULL` 或 `project.provider_id` 不属本租户内任何服务商)
- 服务商侧(scope=provider):看本租户内 + **本服务商接的项目**(`project.provider_id == self_provider_id`)

后端 `supervisor_case_filter` / `supervisor_call_filter` / `supervisor_agent_filter` 三个共享函数封装此逻辑,已应用于 11+ 端点(reviews / risk-events / live-wall / cases / escalated 等)。详 `poc/backend/app/api/_supervisor_scope.py`。

### 3.6 v1.4 治理增量（已交付）

v1.0–v1.3 完成基础多租户结构后，v1.4 落地以下治理与协作要素：

#### 3.6.1 项目（Project）成为一等公民

物业租户内的「项目」是案件归属与数据可见性的最小单元，原模型已存在但未启用，v1.4 全链路接通：

- **Project 模型**：`tenant_id` + `provider_id`（指定承接服务商）+ `property_pm_user_id` / `provider_pm_user_id`（双方项目经理）+ `allow_internal_assist`（项目级开关：服务商承接的项目下，是否允许物业内勤协助）。系统纯粹催收，不区分项目子类型。
- **服务商分配 = 项目级**：物业建项目时选定 `provider_id`，整个项目下的案件默认对该服务商外勤可见
- **法务分配 = 案件级**：保持原有 `LegalConversionOrder` 不变（按金额阈值 + 付费法律服务包）
- **项目经理只读**：`project_manager_property` / `project_manager_provider` 角色登录后，所有 admin 端写操作（导入/分配/释放/转法务/添加备注）均隐藏，看板拖拽禁用，列表 checkbox 隐藏

#### 3.6.2 服务商按项目分配 + 推荐入驻

- **服务商创建**：以平台 ops 创建为主；物业 admin 可推荐入驻（`POST /admin/providers/recommend`），写 `ServiceProvider(audit_status='pending', recommended_by_tenant_id=<本租户>)`，ops 端审核通过后该租户即可在项目上选用
- **agent 可见性**：服务商外勤只看到「自己负责的项目」案件 + 已分配给自己的私海；物业内勤看「无项目案件 + 无服务商项目 + 开了协助开关的项目」公海
- **跨租户隔离**：服务商 admin 可见自己签约的所有租户，但租户 A 的私有数据（如业主姓名/手机号）严格不暴露给租户 B 的视图

#### 3.6.3 双向解约握手 + 30/60 天数据窗口

- **解约流程**：物业或服务商任一方发起 `POST /providers/{id}/terminate-request` → 对方 7 天内确认 `POST /terminate-confirm` → `status='terminated'` + `terminated_at=now`
- **超时兜底**：daily worker `app.workers.scheduled.terminate_timeout` 扫 7 天未确认请求自动转 terminated（写审计 `provider.contract.auto_terminated`）
- **解约后数据窗口**（D3）：
  - `[0, 30) 天`：服务商对历史通话 / 案件**只读**；业主姓名 / 手机号**立即脱敏**
  - `[30, 60) 天`：服务商不可读
  - `≥ 60 天`：daily worker 软删（设 `is_visible=False`）相关通话转写 / AI 分析；案件归物业，不动
- **UI 状态机**：物业 `/admin/providers/:id` 下方「解约管理」面板（申请/等待对方确认/已终止 + 倒计时）；服务商 dashboard 顶部 banner（收到请求 / 自己请求中 / 已终止）

#### 3.6.4 话术库三层归属（D4）

`script_template` 加 `provider_id BIGINT NULL FK service_provider(id)`，三层语义：

| layer | tenant_id | provider_id | 写权限 | 谁能读 |
|-------|-----------|-------------|--------|--------|
| 平台预置 | NULL | NULL | 仅 platform_superadmin | 所有人 |
| 物业私有 | NOT NULL | NULL | 该租户 admin | 该租户内勤 + 该租户分配项目的服务商外勤 |
| 服务商私有 | NULL | NOT NULL | 该服务商 admin | 该服务商外勤（含跨租户作业时） |

- 物业 admin **不可改平台预置**（403），可 `POST /admin/scripts/{id}/fork` 复制为本租户私有再编辑
- 物业 admin **不可读服务商私有**（其数字资产）
- 服务商 admin **不可读物业私有**（同上）
- 通话实时建议引擎（`realtime_llm._load_scripts`）按 caller 角色合并加载：
  - 内勤 → 平台 + 案件归属物业私有
  - 外勤 → 平台 + 案件归属物业私有 + 本服务商私有

#### 3.6.5 P1 标签语义调整

原 P1 = "未上线"；现 P1 = **"已上线但 demo 数据 / UX 待打磨"**。物业 admin sidebar 上「服务商合作」从 P1 摘除（v1.4 已含完整推荐入驻链路）；「数据报表」「合规月报」保留 P1（v1.5 补 demo 数据）。

---

## 4. 角色体系

### 4.1 角色体系总览（10 个角色，3 个层级）

**平台层（有证慧催运营公司内部）**

| 角色 | 英文标识 | 典型人数 | 核心职责 |
|------|----------|----------|----------|
| 平台超管 | `platform_superadmin` | 1-2 人 | 系统技术配置、Prompt 管理、安全审计，不参与日常业务 |
| 平台运营员 | `platform_ops` | 3-10 人 | 开通租户、审核服务商、续费跟进、客户支持，不能改系统配置 |

**服务商层**

| 角色 | 英文标识 | 典型人数 | 核心职责 |
|------|----------|----------|----------|
| 服务商管理员 | `provider_admin` | 1-3 人 | 管理本团队成员、查看各签约物业公司工作量和收益 |

**租户层（物业公司）**

| 角色 | 英文标识 | 典型人数 | 核心职责 |
|------|----------|----------|----------|
| **物业管理员** | `admin`(scope=tenant) | 1-3 人 | 用户管理、全局数据、系统配置、任务发起 |
| 主管/督导 | `supervisor` | 2-5 人 | 管理本组催收员、质检复核、处理升级案件 |
| 催收员(内勤) | `agent` + `work_mode='internal'` | 5-50 人 | 正式员工，日常外呼催收 |
| 催收员(外勤兼职) | `agent` + `work_mode='external'` | 不定 | 合同制/兼职，受限账号，号码脱敏 |
| 法务对接人 | `legal` | 1-3 人 | 处理升级至法务阶段的案件 |
| 运营协调 | `coordinator` | 1-10 人 | 处理通话中产生的维修/投诉工单 |

> **v0.5.6 术语统一**:对外展示文案统一用「物业管理员」(不再裸写「admin」/「管理员」);服务商侧对应「服务商管理员」(`admin` 在 `scope=provider:{id}` 上下文下)。前端 ROLE_LABEL 已集中到 `frontend/src/lib/roleLabel.ts`(SSOT),按 scope 自动选词。代码逻辑里 `role === "admin"` 字段标识符不动。
>
> **v2.2 四维正交角色模型**:催收员的 internal/external 已从单独的 role 收敛为 `agent` + `work_mode` 字段,详见 §16 数据模型。

### 4.1.1 物业 ↔ 服务商 5 角色对齐表(v0.7.0)

人工测试反馈:**「物业的 5 个角色 ↔ 服务商对应的 5 个角色应功能、UI 对齐;只是数据权限有差异」**。v0.7.0 一波收口对齐。原则:

- **同 role 名 + 同 UI 组件 + 同后端端点路径**(`/supervisor/*`、`/agent/*`、`/pm/*`、`/legal/*` 物业服务商共用)
- **scope 决定数据范围**:scope=`tenant:{id}`(物业)vs scope=`provider:{id}:tenant:{id}`(服务商) — 后端在端点入口用 `SupervisorScope` / `provider_id` / `work_mode` 切换 SQL where 子句
- **唯一功能差异**:**仅物业管理员可创建项目 + 导入案件**(服务商管理员无)

| 维度 | 物业侧 | 服务商侧对应 | 功能差异 | 数据范围差异 |
|---|---|---|---|---|
| 管理员 | `admin`(scope=tenant) | `admin`(scope=provider) | 物业 admin 独有:**创建项目**(`POST /admin/projects`)+ **导入业主名单**(`POST /admin/cases/import`)。其余 CRUD / 团队 / 话术 / 结算等完全对称 | 物业 admin 看本租户全部;服务商 admin 看 `project.provider_id == self_provider_id`(唯一约束,不走 ProviderTenantContract) |
| 督导 | `supervisor`(scope=tenant) | `supervisor`(scope=provider) | **无功能差异**(v0.7.0 Wave C 已对齐 nav 15 项);UI 完全一致 | 物业督导:本租户内 + 非服务商接案;服务商督导:本租户内 + 本服务商接的项目案件(`supervisor_case_filter` 守卫) |
| 项目经理 | `project_manager`(scope=tenant)| `project_manager`(scope=provider)| 无功能差异;dashboard PropertyView vs ProviderView 区块结构对称(KPI / 多项目 / Top 5 / 运营提醒) | 物业 PM:管理 `property_pm_user_id == self` 的项目;服务商 PM:管理 `provider_pm_user_id == self` 的项目 |
| 催收员 | `agent` + `work_mode='internal'` | `agent` + `work_mode='external'` | **无功能差异**(工作台 / 提醒中心 / 培训库共用);差异仅在佣金率字段 — 后端 `/agent/me/by-project` 按 `work_mode` 切换 `internal_agent_commission_rate` vs `provider_agent_commission_rate` | 同督导(scope=provider 时仅看本服务商接的案件) |
| 法务 | `legal`(scope=tenant) | `legal`(scope=provider) | **物业法务专属**:`/legal/pending-finalize`(接督导批准的转化请求 → 内部处理) + `/legal/internal-orders`(物业内部对接人完整流程)。**服务商法务专属**:`/provider/legal/requests`(跨多物业转化请求汇总)。两侧职责本就不同 — 服务商法务无内部订单概念 | 物业法务:本租户案件;服务商法务:本服务商承接项目下的案件 |

### 4.2 权限矩阵

| 功能 | 管理员 | 主管 | 内部催收 | 外部兼职 | 法务 | 工单处理 |
|------|:------:|:----:|:--------:|:--------:|:----:|:--------:|
| 创建/停用用户 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 全公司分析报表 | ✅ | 仅本组 | 仅自己 | ❌ | ❌ | ❌ |
| 员工排名看板 | ✅ 完整 | ✅ 本组 | 仅自己排名位置 | ❌ | ❌ | ❌ |
| 公海认领案件 | ✅ | ✅ | ✅ | ✅ 限额 | ❌ | ❌ |
| 查看完整手机号 | ✅ | ✅ | ✅ | ❌ 脱敏 | 仅负责案件 | ❌ |
| 实时 AI 辅助通话 | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| 查看通话录音/转写 | ✅ 全量 | ✅ 本组 | 仅自己 | 仅自己 | 负责案件 | ❌ |
| 案件升级到督导 | ✅ | — | ✅ | ✅ | ❌ | ❌ |
| 申请转法务（提单子）| ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 审批转法务申请 | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **直接移交法务**(v0.6.0,无申请也可越权转,需填原因) | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 法务接单选服务包（v0.5.4）| ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| 上报 admin（减免单/转法务单）| ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 督导侧案件动作（催回访/催办/介入/重派）| ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| 发送缴费链接 | ✅ | ✅ | ✅ 自己案件 | ✅ 自己案件 | ❌ | ❌ |
| 处理法务案件 | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| 处理工单 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| 话术库配置 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 导出数据 | ✅ | 本组 | 仅自己 | ❌ 禁止 | 负责案件 | ❌ |
| 系统配置 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

**v0.5.4 注**:
- 案件升级链已收窄为 **一级**(催收员→督导),取消「督导→admin 案件 transfer」(督导接案后自己负责到底)
- 重大事项走**审批单**(减免/转法务)而非案件 transfer;督导可在审批单上点「上报 admin」转交 admin 决

### 4.3 内部催收员 vs 外部兼职催收员

| 维度 | 内部催收员 | 外部兼职催收员 |
|------|-----------|---------------|
| 账号创建方式 | 管理员直接创建，设初始密码 | 管理员生成邀请链接（7天有效），兼职自行注册（需实名：姓名+手机） |
| 手机号显示 | 完整显示 139-8228-2386 | 脱敏显示 139\*\*\*\*2386 |
| 公海认领上限 | 50 条/人 | 10 条/人 |
| 升级路径 | 可转主管/法务 | 只能转主管 |
| 账号有效期 | 无限制 | 管理员可设到期日，到期自动停用 |
| 可访问时段 | 无限制 | 可配置（如仅工作日 9:00-18:00）|
| 数据导出 | 仅自己相关数据 | **禁止任何导出** |
| PC 工作台 | ✅ 可登录 PC | ❌ 仅限 App |

### 4.4 法务转化双路径(v0.6.0)

法务转化有两条互斥路径,后端 `POST /supervisor/cases/{id}/transfer-legal` 校验本案件无 pending 申请(409 防双轨):

**路径 A:催收员申请 → 督导审批(主流程)**

```
催收员 RequestLegalConversionModal(选预设原因 + 备注)
  → POST /agent/cases/{id}/intent  body={action:"transfer_legal", note}
  → 写 LegalConversionRequest(status=pending,requester_role=agent)

  ↓ 督导侧:案件详情页按钮条件渲染

if (case.pending_legal_conversion_request_id != null) {
  显示「审批转法务」按钮 → 打开 LegalConversionApprovalModal
  → POST /legal-conversion-requests/{id}/approve|reject
  → 状态 → approved_pending_legal / rejected
} else {
  显示「移交法务」按钮 → 路径 B
}
```

**路径 B:督导直接移交(越权,v0.6.0 新)**

```
督导 TransferLegalDirectModal(必填原因)
  → POST /supervisor/cases/{id}/transfer-legal  body={reason}
  → 后端校验:本案件无 LegalConversionRequest status ∈ (pending, pending_admin)
              否则 409 ERR_PENDING_REQUEST_EXISTS
  → case.stage = 'legal'
  → 写 audit log(action=case.supervisor_transfer_legal_direct,payload={reason})
  → 通知原催收员「案件已直接转法务」
```

**为何提供路径 B**:业主长期失联 + 大额欠费 + 资产线索充足的案件,无需催收员介入即可直接进法务流;但写明 audit reason 留痕可追溯,防止滥用。

---

## 5. 用户创建与账号管理流程

### 5.1 内部用户创建（v1.4 方案 A — 无初始密码 + OTP 首登）

```
管理员 → 用户管理 → 新建用户
    ↓
填写：姓名 / 手机号 / 角色（不填密码）
    ↓
系统创建 UserAccount，password_hash 写入随机占位（不可命中）
    ↓
员工首次登录：登录页选「手机验证码」tab，输入手机号
    ↓
获取验证码 → 输入 6 位 OTP → 登录成功
    ↓
（可选）登录后在「我的账号」自愿设置密码以后用密码登录
```

**为什么不强制初始密码**：admin 给基层员工设密码 → 通知 → 员工记 = 三重摩擦；
我们已落地 OTP 通道（`/auth/otp/send|verify`），员工手机号天然就是 App 拨号绑定号，零摩擦。

**后端实现**：`UserCreateByAdminRequest.password` 改为 Optional；未传时
`UserAccount.password_hash` 写入 `bcrypt(secrets.token_urlsafe(48))`（实际不可登录），
`login_method='otp'` 标记偏好。如需 admin 仍想给一个初始密码（特殊场景），传 `password` 字段也支持。

### 5.2 外部兼职邀请注册

```
管理员 → 用户管理 → 邀请外部兼职
    ↓
配置：认领上限 / 账号到期日 / 可访问时段
    ↓
系统生成唯一邀请链接（7天有效，单次使用）
    ↓
管理员将链接发给兼职人员（微信/短信）
    ↓
兼职人员打开链接 → 填写姓名+手机+验证码（实名绑定）
    ↓
账号激活，仅限 App 登录，权限受限
```

### 5.3 工单处理员/法务账号

```
管理员直接创建，分配对应角色
法务：只看到「法务案件」模块
工单处理员：只看到「工单管理」模块
两者均无法看到催收数据、通话录音
```

### 5.4 账号安全策略

本系统处理通话录音、业主个人信息和法律存证数据，执行金融/法务行业安全标准。

#### 密码规则

| 规则 | 要求 |
|------|------|
| 最小长度 | 8 位 |
| 复杂度 | 必须同时包含：大写字母 + 小写字母 + 数字 + 特殊字符（`!@#$%^&*`）|
| 禁止 | 与手机号/姓名相同；连续重复字符超过 3 位（如 `aaa`）|
| 有效期 | 90 天强制修改；到期前 7 天提醒；到期后登录即跳转修改页 |
| 历史限制 | 不得与最近 5 次密码相同 |
| 初始密码 | 系统生成 10 位随机密码，首次登录强制修改 |

#### 登录安全

| 规则 | 要求 |
|------|------|
| 连续失败锁定 | 5 次失败 → 锁定 30 分钟；10 次失败 → 永久锁定（须管理员解锁）|
| JWT 有效期 | 平台超管 8h；租户管理员/督导 12h；内部催收员 24h；外部兼职 8h（与可访问时段联动）|
| 多端互踢 | 同一账号只允许一台 App 或一台 PC 在线；新设备登录自动踢掉旧设备并推送 FORCE_LOGOUT |
| MFA | 平台超管**强制**开启 TOTP（Google Authenticator 等）；租户管理员**可选**开启 |
| 操作超时 | 30 分钟无操作自动注销（PC 端；App 端 4 小时）|

#### 短信通道

所有系统短信（账号激活/密码重置/支付通知）统一使用**阿里云短信服务（阿里云 SMS）**：
- 签名：`有证慧催`
- 模板：账号激活、密码重置、邀请链接、支付确认（每类独立审批）
- 发送频率限制：同一手机号每分钟最多 1 条、每天最多 10 条

### 5.5 登录方式（v1.4 已实施）

> 完整账号体系演进设计见 `docs/account-architecture.md`（v1.5 推进中）。
> 本节为已上线状态。

登录页提供 **2 种登录方式**（tab 切换），所有角色统一同一入口：

#### 方式 A：账号 + 密码

「账号」字段后端自动识别为以下 3 种之一：

| 输入格式 | 识别为 | 说明 |
|----------|--------|------|
| 11 位数字 `^1[3-9]\d{9}$` | 手机号 | 全角色通用，存储用 AES-256 加密 |
| 18 位大写字母数字 `^[0-9A-Z]{18}$` | 统一社会信用代码 | 物业租户专用，登录后自动定位到该租户的第一个 admin 用户 |
| 含 `@` | 邮箱 | 组织管理员可绑定（v1.5 转为主登录入口） |

后端端点：`POST /api/v1/auth/login-universal`（body: `{account, password}`）

#### 方式 B：手机号 + 短信验证码

- 输入 11 位手机号 → 点「获取验证码」→ `POST /auth/otp/send`
- 后端生成 6 位 OTP，5 分钟有效，60 秒频率限制
- dev 模式直接在响应里回传 OTP（生产环境通过阿里云 SMS 发送）
- 输入验证码 → `POST /auth/otp/verify` → 返回 token

#### 忘记密码

`POST /auth/password-reset/request`（手机号）→ 发送 OTP（用户不存在不报错防探测）→
`POST /auth/password-reset/confirm`（手机号 + OTP + 新密码）→ 改密成功

#### 各角色推荐登录方式

| 角色 | 推荐 | 备选 |
|------|------|------|
| 平台超管 / 平台运营员 | 账号 + 密码（手机号或邮箱）+ TOTP MFA | — |
| 物业公司管理员 | 账号 + 密码（**社会信用代码** 或手机号或邮箱） | — |
| 服务商管理员 | 账号 + 密码（手机号或邮箱） | — |
| 主管 / 内部催收员 / 法务 / 工单 / PM | 手机 + OTP | 手机 + 密码 |
| 外部兼职催收员（仅 App） | 手机 + OTP | 手机 + 密码 |

---

## 6. 手机号隐私化方案

### 6.1 存储与显示

```
数据库存储：AES-256 加密的完整手机号
           ↓
API 层根据调用方角色决定返回内容：
  内部员工 → 139-8228-2386（完整）
  外部兼职 → 139****2386（中间 4 位掩码）
  法务      → 仅案件关联的业主号，完整
  工单      → 不返回手机号字段
```

### 6.2 实时通话中的号码处理

```
外部兼职在 App 点击「拨打」
    ↓
App 发请求：POST /api/calls/dial/{case_id}
    ↓
后端解密真实号码，生成 Android dial Intent
返回给 App（Intent 直接触发系统拨号，不经过 App UI 展示层）
    ↓
App 界面全程显示脱敏号码
Android 系统拨号界面短暂显示完整号码（系统行为，无法避免）
    ↓
通话接通后系统界面消失，App 界面接管，继续显示脱敏
```

### 6.3 通话转写中的号码脱敏

所有 ASR 转写文本存库前，后端正则处理：
```python
re.sub(r'(1[3-9]\d)\d{4}(\d{4})', r'\1****\2', transcript)
# 13982282386 → 139****2386
```

---

## 7. 管理员分析看板内容

### 7.1 公司管理员（全局视角）

```
今日实时概览
┌────────┬────────┬────────┬────────┐
│今日拨打 │有效接通 │转化成功 │本月回款 │
│  234   │  156   │   42   │¥86,400 │
└────────┴────────┴────────┴────────┘

催收进度漏斗（本月）
待联系(342) ──▶ 跟进中(89) ──▶ 承诺缴(54) ──▶ 已缴费(156)

催收员排名（本月，管理员可见完整）
┌──┬──────┬──────┬──────┬──────┬──────┐
│排 │姓名  │拨打量 │接通率 │转化率 │回款额 │
│1  │王小明│ 312  │ 68%  │ 28%  │¥12万 │
│2  │李红  │ 298  │ 71%  │ 25%  │ ¥9万 │
└──┴──────┴──────┴──────┴──────┴──────┘

公海状态 / 积压告警 / 升级案件统计
```

### 7.2 主管（本组视角）

- 仅看自己组内催收员的数据
- 组内排名（完整）
- 本组升级案件处理进度

### 7.3 催收员（个人视角）

- 自己今日/本月的拨打量、转化率、回款额
- 自己在团队中的排名位置（第 X 名，不看他人详情）
- 私海案件状态分布

---

## 8. 功能模块清单

### 8.1 Android App（外呼员）

| 模块 | 优先级 | 描述 |
|------|--------|------|
| 催收任务列表 | P0 | 私海案件列表（欠费金额/月数/优先级/最后联系），支持按状态筛选 |
| 公海浏览与认领 | P0 | 内部员工可从公海认领案件到私海（外部兼职限额） |
| 一键拨号（App 主控） | P0 | 点击案件直接发起通话，自动建立 CallSession |
| PC 触发拨号（PC 主控） | P0 | PC 点击拨打 → App 弹出「立即拨打张三？」通知 → 员工点击发起 |
| **实时 AI 话术提示** | P0 | 通话中三段式界面：顶部通话控制栏 / 中部业主信息+实时对话 / 底部 AI 建议卡片 |
| 风控提醒与挂断 | P0 | L1震动提示 / L2全屏警告 / L3程序化挂断（InCallService） |
| 通话后快速标记 | P0 | 挂机后弹窗预填 AI 识别结果，一键确认 |
| 支付二维码展示 | P0 | 通话中可调出业主专属支付二维码（大图，可给业主扫描）|
| 业主历史预览 | P1 | 拨号前查看历史通话摘要和欠费情况 |
| 录音上传模式 | P0 | 支持实时推流与事后上传两种模式（详见 8.3），具体模式由管理员配置，App 无任何存储地址设置项 |
| 今日绩效小结 | P1 | 当天外呼成果总结 |

### 8.2 PC 端（管理/督导/法务/工单）

| 模块 | 优先级 | 描述 |
|------|--------|------|
| **通话实时工作台（三栏）** | P0 | App 或 PC 发起通话后自动弹出：左栏业主信息、中栏实时对话、右栏 AI 建议+快捷操作 |
| 快捷操作面板 | P0 | 一键：发支付二维码/链接、建工单、转主管、转法务 |
| 催收 CRM 列表视图 | P0 | 全案件列表，支持筛选（员工/阶段/欠费金额/时间）、排序、批量操作 |
| 催收 CRM 看板视图 | P0 | 按阶段分列：待联系/跟进中/承诺缴费/已缴费/升级中 |
| 案件详情页 | P0 | 左侧业主信息+欠费详情，右侧活动时间线（历次通话摘要+跟进记录+状态变更） |
| 公海/私海管理 | P0 | 公海列表、分配操作、各员工私海数量看板 |
| 业主名单导入 | P0 | Excel/CSV 批量导入，字段映射，重复检测 |
| 录音批量上传+事后分析 | P0 | 批量上传，ASR+LLM 流水线，查看结果 |
| 管理员分析看板 | P0 | 今日概览、漏斗、排名、公海状态 |
| 督导复核工作台 | P1 | 仅显示需复核通话，支持播放片段、修改标签 |
| 风控记录与回放 | P1 | 风控事件时间线，点击跳转录音对应时间点 |
| 工单管理 | P1 | 工单处理员的待办/处理中/已完成工单列表 |
| 法务案件管理 | P1 | 法务专员的案件队列，含历史通话摘要和文档 |
| 话术库管理 | P1 | 按异议类型维护话术模板 |
| 用户与角色管理 | P1 | 创建内部用户、生成外部邀请链接、设账号有效期 |
| 数据分析报表 | P1 | 转化率趋势、未明确原因分布、员工效率对比 |
| **PC 实时通话墙** | P1 | (v1.3) 主管/管理员/项目负责人物业可见所有正在通话的坐席卡片；点击进入实时跟单页（详 §11.7）|
| **PC 引导手机端 + Help 页** | P1 | (v1.3) 首次登录弹引导 modal（含 APK 下载二维码 + "不再提示"）；常驻 `/help/app` 公开页（不登录可访问），含安装步骤 / 权限授予 / MIUI 录音目录设置 / 服务器地址扫码注入说明（实施细节见本节末）|
| 系统配置 | P2 | 风控关键词自定义、通知规则、AI 推送灵敏度、数据保留策略（**存储后端地址/OSS 凭证等基础设施配置仅在服务器端 .env 维护，不在任何前端界面暴露**）|

**「PC 引导手机端 + Help 页」实施细节（v1.3）**

后端：
- `UserAccount.preferences JSONB` 存个人偏好，关键 key：`app_intro_dismissed: bool`
- `GET /api/v1/users/me/preferences` 任何认证用户读
- `PATCH /api/v1/users/me/preferences` 局部 merge 更新
- `GET /api/v1/public/app-info` **无需认证**，返回当前部署的 APK url / 版本 / 系统要求 / 权限说明（部署时通过环境变量 `AUTOLUYIN_APK_URL` / `AUTOLUYIN_APK_VERSION` 注入）

前端：
- 首次登录后 AuthenticatedShell 检查 `preferences.app_intro_dismissed`：false → 弹 `AppIntroModal`（含 QR + 4 章节摘要 + "不再提示"勾选）
- 公开页 `/help/app`（不登录可访问，所有角色可分享给坐席）：完整 4 章节（为什么需要 / 安装步骤 / 权限授予含 MIUI 注意事项 / 服务器地址扫码注入）
- 主菜单常驻入口（避免一次性 modal 关掉就找不到）

#### 各角色菜单/工作台 v0.6.0 增量

| 角色 | 入口 | 内容 |
|------|------|------|
| **催收员**(agent)| nav 新增「提醒中心」`/agent/reminders`(图标 Bell)| 整合 3 类软提醒(承诺到期 72h / 法务申请状态变化 / 案件 SLA 告警 30d 停滞) + 站内信(mark-read / read-all);后端 GET `/agent/me/reminders/synthetic` |
| **催收员**工作台 | KPI bar 下方加「我的项目」横滚卡片条 | 按项目分组展示:案件数 / 本月缴清数 / 已回款金额 / 预估佣金(按 work_mode internal/external 走 project.internal/provider_agent_commission_rate) |
| **物业管理员**(admin)| 「结算与报表」段(v0.5.9 已加 2 项) | 新增 settlement_statement.billing_method 字段中文映射;法务转化页加「区块链存证」section |
| **服务商管理员**(provider admin)| 「结算与报表」段(v0.5.9 已加 1 项) | 同物业 admin 计费方式中文化 |
| **物业/服务商项目经理**(project_manager)| dashboard 顶部加「运营提醒」5 卡片网格(GET `/pm/dashboard/alerts`)| 5 类:审批积压 / 承诺逾期未催 / 坐席 7 天无通话 / 本月分钟超 2000 / 案件 stage 停留 >14 天;count>0 时整张卡片 Link 到 detail_path |
| **物业督导**(supervisor)| 案件详情 + 升级案件 + 承诺催付 + 超期预警 + 风险事件 5 页大重构 | 法务转化按钮条件渲染 / 升级案件 4→2 按钮(介入处理 5 选项弹窗)/ 承诺催付催回访接通真实 API / 超期预警重派 + 释放公海实装后端 / 风险事件 EventDetailModal 加可写处置区(status + handle_result_note) |

### 8.3 录音上传模式配置

App 支持两种录音工作模式，能力差异如下：

| 模式 | 原理 | AI 能力 | 适用场景 |
|------|------|---------|---------|
| **模式 A：实时推流** | 通话中音频逐帧推送后端 | 实时话术辅助 + 风控 + 事后分析 | 网络稳定的办公/呼叫中心场景 |
| **模式 B：事后上传** | 本地录音完整保存，通话结束后上传 | 仅事后分析（无实时 AI 辅助） | 网络不稳定或移动外勤场景 |

**模式 A 是核心产品价值**，模式 B 是保底兜底。

#### 管理员配置策略（租户级）

管理员在「系统配置 → 录音模式」中统一设置，**App 端无任何可见配置项**：

| 策略选项 | 说明 | 推荐场景 |
|---------|------|---------|
| 强制实时（模式 A） | 所有员工只能使用实时推流；网络不可用时通话功能受限 | 呼叫中心，网络有保障 |
| 强制事后上传（模式 B） | 所有员工本地录音后上传；无实时 AI | 合规要求高但网络差的团队 |
| **优先实时，自动降级**（默认推荐） | App 检测网络质量：质量好 → 实时推流；质量差/断线 → 自动切本地录音，通话结束后上传补传 | 大多数场景 |

**「优先实时，自动降级」细节：**
```
通话开始 → App 检测网络（RTT <150ms 且带宽 >100kbps → 实时模式）
    ├─ 实时推流成功 → 正常实时 AI 辅助
    └─ 实时推流失败（断线/超时）→ 自动切本地录音
           ↓ 通话结束
        本地文件上传 → Celery 任务触发事后 ASR + LLM 分析
        App 通知：「本次通话已转为录音模式，AI 分析将在上传完成后显示」
```

#### 角色级覆盖（可选，v1.1）

v1.1 支持管理员为特定角色或特定用户覆盖租户默认策略，例如：
- 外部兼职催收员统一强制「事后上传」（网络环境不可控）
- 内部核心催收员强制「实时推流」（确保 AI 辅助质量）

### 8.4 Android 设备与录音兼容性矩阵（v1.9.9）

#### 8.4.1 核心原则

App **自己不直接录通话音频**：Android 9 起 Google 在系统层封禁了 `AudioSource.VOICE_CALL` 通道，第三方应用无法获取对方语音。本系统的方案是：

> **依赖手机 ROM 内置的"通话自动录音"功能** → 通话挂断后 App `RecordingScanner` 扫描系统录音目录 → 按号码 + 时间窗口 + 文件大小三层匹配 → 上传后端 ASR

因此"App 录音可用性"等价于"手机 ROM 是否保留了系统通话录音功能 + 录音文件是否对第三方应用可读"。

#### 8.4.2 兼容性矩阵

| Android 版本 | 原生 (Pixel / AOSP) | MIUI / HyperOS（国行） | EMUI / HarmonyOS（国行） | ColorOS / OriginOS（国行） | 海外版（任意品牌） |
|---|---|---|---|---|---|
| **6 / 7** | ✅ 完全可用 | ✅ | ✅ | ✅ | ✅ |
| **8 / 9** | ❌ 系统封禁 | ✅ MIUI 9/10/11 | ✅ EMUI 8/9/10 | ✅ ColorOS 5/6/7 | ❌ |
| **10** | ❌ | ✅ MIUI 12 | ✅ | ✅ | ❌ |
| **11** | ❌ | ⚠️ MIUI 12.5（需用户手动开启"通话录音"开关 + 给 App"所有文件访问权限"） | ⚠️ | ⚠️ | ❌ |
| **12** | ❌ | 🟡 MIUI 13（部分机型砍除） | 🟡 | 🟡 | ❌ |
| **13 / 14 / 15** | ❌ | 🟡 HyperOS（按机型，多数继续保留） | 🟡 | 🟡 | ❌ |

✅ = 默认开箱可用 / ⚠️ = 可用但需额外配置 / 🟡 = 部分机型可用 / ❌ = 系统级封禁

#### 8.4.3 选机指引（采购建议）

| 等级 | 组合 | 适用 |
|---|---|---|
| **A. 最稳** | Android 6/7 + 任何国行 ROM | 内部测试机、低预算客户 |
| **B. 推荐** | Android 8/9 + MIUI 10/11 | 生产环境主力，最贴近实际坐席用机 |
| **C. 可用** | Android 10/11 + MIUI 12/12.5 | 较新设备，但需培训坐席开启录音开关 |
| **D. 谨慎** | Android 12+ + 国行 MIUI 13/HyperOS | 上架前必须**单机实测**录音可用 |
| **E. 拒绝** | Pixel、海外版任何品牌、Android 10+ AOSP | **明确不支持**，合同里写明 |

#### 8.4.4 APK 构建参数

| 字段 | 取值 | 说明 |
|---|---|---|
| `minSdk` | 23（Android 6.0） | 覆盖最低端测试机；正式上线根据客户机型分布可上调到 26/28 |
| `targetSdk` | 29（Android 10） | 避免 MIUI 老版本 PackageParser "匹配度不够"误报 |
| `compileSdk` | 35（Android 15） | AGP 8.5.x 要求；不影响安装兼容性 |
| 签名方案 | v1 + v2 双签 | MIUI 10 / Android 8 era 部分机型只识别 v1，须双签 |

清单中**禁止**出现以下 API 29+ 才存在的属性（老 PackageParser 会拒绝解析）：
- `<service ... android:foregroundServiceType="..." />` — API 29 引入
- `<application ... android:requestLegacyExternalStorage="true">` — API 29 引入
- `<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />` — API 34 引入

如未来需支持 Android 14+，应通过 manifest merger 按 SDK 分层注入（`tools:targetApi`）。

#### 8.4.5 录音文件候选目录

`RecordingScanner.defaultCandidateDirs` 维护各 ROM 录音落盘路径：

| ROM | 录音目录 | 文件后缀 |
|---|---|---|
| MIUI 8/9/10 | `/storage/emulated/0/MIUI/sound_recorder/call_rec/` | `.m4a` / `.mp3` |
| MIUI 11/12+ | `/storage/emulated/0/MIUI/sound_recorder/call/` | `.m4a` |
| EMUI 8/9/10 | `/storage/emulated/0/Sounds/CallRecord/` | `.m4a` / `.amr` |
| ColorOS | `/storage/emulated/0/Recordings/Call/` | `.m4a` |
| AOSP（早期） | `/storage/emulated/0/Recordings/` | `.amr` |

候选目录可由 `/api/v1/devices/{id}/config` 下发（运行时配置 L2），不需要重打 APK 即可适配新机型。

#### 8.4.6 上线前选机与合同条款建议

- **测试机最低覆盖**：至少 2 台 — Android 6 + MIUI 10（最宽松）+ Android 9 + MIUI 11（贴近生产）
- **合同明文**：列出"支持机型 ROM 矩阵"作为附件，客户买不在矩阵内的机器导致录音抓不到，不承担售后责任
- **租户层兼容性策略**（v2.0 规划）：在 `tenant_config` 增加 `device_compatibility_policy` 字段（`strict_whitelist` / `warn_only` / `disabled`），App 自检时上报机型+ROM，后端按策略判断是否允许该设备入网

#### 8.4.7 风险与缓解

| 风险 | 严重度 | 缓解 |
|---|---|---|
| 客户购入 Android 12+ HyperOS 机型，部分子机型砍录音 | 高 | 上述 §8.4.6 device_compatibility_policy；坐席入职流程加入"录音自检"步骤 |
| Google 进一步收紧 Android 16+ 录音权限 | 中 | 提前调研 VoIP 桥接方案（接 SIP 网关 / 第三方语音中继）作为方案 B |
| 海外版手机走私进入国内市场 | 低 | 自检通过 `Build.MANUFACTURER` + `Build.BRAND` + ROM 字符串识别后拒绝 |
| 录音目录用户手动改路径 | 低 | 候选目录走运行时配置，客服可远程下发新路径 |

#### 8.4.8 客户端能力探测与降级流程（v2.1）

v2.1 sprint 解决"新机型坐席默默失败"问题：通过 **探测 + 表态 + 留痕** 三段式，让坐席与管理员都明确知道每台设备的真实录音能力，并在不可用时主动降级而非默默丢数据。

##### 状态机

```
首次启动 → Onboarding 4 步 Wizard
              ├─ 1. 权限授予（CALL_PHONE / RECORD_AUDIO / READ_PHONE_STATE / READ_CALL_LOG /
              │      READ_CONTACTS / READ_MEDIA_AUDIO / POST_NOTIFICATIONS 等 7 项）
              ├─ 2. 后端地址配置 +「测试连接」
              ├─ 3. 录音设置 — 显示本机 ROM 厂商标签（"MIUI 设备"/"EMUI 设备"/"海外/AOSP"）
              │      + 文案"请到系统设置开启通话自动录音" + checkbox 强制勾选
              ├─ 4. 完成清单 → markOnboardingDone
              └─ 跳 MainActivity → 登录 → doSelfCheck

doSelfCheck → POST /api/v1/devices/self-check {
                  manufacturer, model, android_version,
                  recording_toggle_self_reported,   // Onboarding step 3 勾选值
                  last_recording_scan_failed         // 上次通话扫描结果
              }
            → 后端 derive_capability(rom, android_major) 走静态矩阵
              + last_scan_failed=True 强制降级 incompatible
              ↓
            → 持久化 SharedPreferences (KEY_CAPABILITY / KEY_GUIDANCE / KEY_ROM_LABEL)
            → 写一行 device_capability_log（留痕 + PC 管理员可查历史）
            → 响应 capability + guidance_text → App 持久化

通话挂断 → CallWatcherService.matchAndUpload
            ├─ RecordingScanner 找不到录音文件 → AppConfig.markRecordingScanFailed(true)
            │      下次 self-check 触发 capability=incompatible
            └─ 找到文件 + 上传成功 → markRecordingScanFailed(false) 清标志
                  下次 self-check 回到矩阵判定（单向收紧，不反向自动升级）

WebView 端
- JsBridge.getCapability() 同步返回 JSON
- /app/home   顶部 banner（绿可关 / 橙不可关含详情链接 / 红粗体不可关）
- /app/profile "录音能力" section（含 ROM + guidance + 上次检测时间）
- /app/cases/:id 拨号前 incompatible 弹 confirm

PC 管理员
- /admin/agent-devices 坐席设备列表（capability 筛选 + 模糊搜索 + 自检历史 Drawer）
- /supervisor/live-wall 坐席卡片右上 cap-badge（绿 / 橙 / 红 / 灰）
```

##### capability 四档定义

| 档位 | 触发条件 | UI 表现 | 业务行为 |
|---|---|---|---|
| `realtime` | 静态矩阵命中 ✅ + 未实测失败 | 绿色 banner（可关闭）| AI 实时分析 + 风控 L1/L2/L3 |
| `post_upload` | 静态矩阵命中 ⚠️/🟡 + 未实测失败 | 橙色 banner（不可关 + 详情链接） | 通话挂断后上传，事后分析 |
| `incompatible` | 矩阵命中 ❌ **或** `last_recording_scan_failed=True` | 红色 banner（粗体不可关）| 可拨号但无 AI 分析，拨号前弹 confirm |
| `unknown` | 从未自检过（新设备未登录）| 不展示 banner（profile 显示"未检测"灰标签）| 等待首次自检 |

##### 静态矩阵优先级

1. 客户端上报 `manufacturer` + `android_version` + `model`
2. 后端 `services/device_capability.py:CAPABILITY_MATRIX` 静态判定（与 §8.4.2 表格一致）
3. 客户端上报 `last_recording_scan_failed=True` **覆盖矩阵** → 强制 `incompatible`
4. 客户端上报 `last_recording_scan_failed=False` → 维持矩阵结果（不反向自动升级，避免抖动骚扰用户）
5. 后端按规则写 `device_capability_log.source`：
   - `static_matrix` — 纯矩阵判定
   - `runtime_verified` — 被 last_scan_failed 覆盖到 incompatible
   - `manual_override`（预留）— v2.x 管理员后台强制覆盖

##### 与 § 8.3 TenantSettings.recording_mode 的关系

`TenantSettings.recording_mode` (`live` / `post` / `auto`) 是 **租户偏好**，
`device.capability` (`realtime` / `post_upload` / `incompatible`) 是 **设备实际能力**。

冲突时 **设备能力为准**：
- 即使租户偏好 `live`，capability=incompatible 的设备仍走"无录音模式"（拨号前 confirm 提醒）
- 即使租户偏好 `post`，capability=realtime 的设备可被管理员强制 live（v2.x 预留 manual_override）
- capability=post_upload 与 recording_mode=live 冲突时，UI 提示用户"该设备不支持实时分析，已自动切换为事后上传"

UI 区分：
- "实时/事后"badge 显示 `TenantSettings.recording_mode`
- "实时可用/事后上传/录音不可用"显示 `device.capability`

##### device_capability_log 数据留痕

| 字段 | 用途 |
|---|---|
| `tenant_id` + `agent_user_id` + `device_id` | 多租户隔离 + 坐席粒度 |
| `manufacturer` / `model` / `android_version` / `rom_label` | 客户端上报原始值（便于回头扩矩阵）|
| `capability` | 本次自检判定结果（4 档之一）|
| `recording_toggle_self_reported` | Onboarding 勾选值 |
| `last_recording_scan_failed` | 是否覆盖矩阵 |
| `source` | static_matrix / runtime_verified / manual_override |
| `created_at` | 时间戳，PC 管理员可查每次自检历史 |

每次 self-check 写一行（不去重），管理员 Drawer 看时间倒序列表。便于：
- 漂移分析（同一设备 capability 跳变追溯）
- 矩阵迭代（统计被 runtime_verified 覆盖的机型 → v2.2 调矩阵）
- 客户支持（坐席投诉时回查"该设备到底走的哪档"）

##### 风险与缓解

| 风险 | 缓解 |
|---|---|
| 用户无脑勾 Onboarding step 3 checkbox（自报录音已开，实际未开）| RecordingScanner 通话后运行时验证兜底，扫不到文件即 markFailed → 下次自检降级 |
| 静态矩阵漂移（新机型 / 新 Android 上市）| `runtime_verified` 优先级高于矩阵；device_capability_log 留痕便于 v2.2 调矩阵 |
| 老 App 升级（不传新字段 recording_toggle_self_reported / last_recording_scan_failed）| 后端 schema 字段全 nullable + 默认走纯矩阵；capability 默认 "realtime" 不破坏老 UI |
| 偶发录音漏抓导致误降级 | v2.x 加 "连续 N 次失败再降级" 阈值（当前单次失败即降级，保守起见接受误判）|
| 离线场景 banner 长期停留旧 capability | profile 显示"上次检测时间"，超 24h 加灰标签提示"数据可能过期"（待 v2.x）|


### 管理员

1. 作为**管理员**，我希望创建内部员工账号时直接设置角色和所属主管，以便新员工当天即可开始工作
2. 作为**管理员**，我希望生成兼职邀请链接并设置账号到期日和认领上限，以便合同结束后账号自动停用
3. 作为**管理员**，我希望在分析看板看到每个催收员的排名和回款额，以便识别优秀员工话术并用于培训
4. 作为**管理员**，我希望在员工通话时 PC 自动弹出三栏工作台，以便随时监听和一键转接
5. 作为**管理员**，我希望大额案件失联多次后自动升级到主管，以便不需要手动跟踪每条案件
6. 作为**管理员**，我希望外部兼职永远看不到完整手机号且不能导出数据，以便防止业主信息外泄

### 内部催收员

1. 作为**内部催收员**，我希望打开 App 看到按优先级排序的私海列表，以便不需要自己判断先打谁
2. 作为**内部催收员**，我希望通话中 AI 实时推送话术卡片，以便应对业主各种异议
3. 作为**内部催收员**，我希望通话中一键展示支付二维码让业主扫描，以便当场完成缴费引导
4. 作为**内部催收员**，我希望遇到骂人时手机自动警告，以便保护自己同时触发督导介入
5. 作为**内部催收员**，我希望挂机后系统预填分析结果，以便一键确认不用填表

### 外部兼职催收员

1. 作为**外部兼职催收员**，我希望只用手机 App 就能完成工作，以便不需要到办公室
2. 作为**外部兼职催收员**，我希望看到脱敏的手机号并能直接拨打，以便不能私下联系业主
3. 作为**外部兼职催收员**，我希望能从公海认领案件（在配额内），以便自主安排工作节奏

### 主管/督导

1. 作为**主管**，我希望只看到本组数据和排名，以便聚焦团队管理不被其他组数据干扰
2. 作为**主管**，我希望接到大额案件升级通知并能立即查看历史通话摘要，以便接手时快速了解背景
3. 作为**督导**，我希望只审核 AI 标记的高风险通话，以便质检时间 < 1 小时/天

### 法务专员

1. 作为**法务专员**，我希望看到分配给我的案件队列（含历史通话摘要），以便了解背景无需重新调查
2. 作为**法务专员**，我希望在系统内记录法务进展（律师函/立案状态），以便主管可以追踪进度

### 工单处理员

1. 作为**工单处理员**，我希望看到催收通话中产生的工单（含业主描述的问题摘要），以便快速处理并回复

### 服务商管理员

1. 作为**服务商管理员**，我希望在一个账号下看到所有签约物业公司的案件和收益汇总，以便统一管理团队工作
2. 作为**服务商管理员**，我希望每月系统自动生成各客户的结算单草稿，以便不需要手动统计工作量
3. 作为**服务商管理员**，我希望查看每位成员在各客户公司的工作量和收益明细，以便核算成员薪酬
4. 作为**服务商管理员**，我希望对有争议的结算单提交异议并附说明，以便与物业公司协商修正

### 物业公司管理员（结算视角）

1. 作为**管理员**，我希望在结算管理页看到本月各服务商的应付金额和明细，以便核实后一键确认
2. 作为**管理员**，我希望为每个服务商合约单独配置结算规则（计费方式/单价/周期），以便灵活管理不同合作模式
3. 作为**管理员**，我希望上传付款凭证后结算单自动标记为已付款，以便保留完整的付款记录
4. 作为**管理员**，我希望查看历史结算趋势图（按月/按服务商），以便控制外包催收成本

---

## 10. 核心流程

### 10.1 实时辅助外呼（双端联动，两种发起方式）

> **PC 同步硬约束**（v1.3 落地）：坐席必须**在 App 内点击「拨打」入口**才会同步给 PC 实时通话墙；
> 绕开 App 直接用系统拨号器发起的电话，由于 PhoneStateReceiver 拿不到号码与案件关联，
> **PC 端不会显示，事后录音也不会上传**。这是有意的隐私边界（避免坐席私人电话被误同步）。

**方式 A：App 主控（员工在外/移动场景）**
```
App 催收列表 → 点击「拨打」
    ↓ POST /api/v1/calls/dial-start  (v1.3, PRD §11.7)
    ↓   - 决议 recording_mode (live/post) 并冻结到 CallRecord
    ↓   - 软配额检查：剩余 ≥3 分钟才放行
    ↓   - 部分唯一索引防同一坐席并发拨号 (409)
    ↓   - WS /ws/supervisor 广播 call.started
    ↓ 后端建立 CallSession
PC 实时通话墙立即显示该坐席卡片（主管/管理员/项目负责人物业可见）
App 显示三段式通话界面 + 30s 一次心跳保活
```

**方式 B：PC 主控（员工坐工位/呼叫中心场景）**
```
PC 催收列表 → 点击「拨打」按钮
    ↓ POST /api/calls/initiate
    ↓ WebSocket 推送 DIAL_REQUEST 给员工 App
App 弹出通知「立即拨打 张三？」→ 员工点击 → 系统拨号
    ↓ Android OFFHOOK 上报
    ↓ 后端广播 CALL_STARTED
PC 自动展开三栏工作台
```

**通话中（两种方式汇合后完全一致）：**
```
App 采集音频 → PCM 帧推流 → 后端 ASR → 转写文本
    ↓（每句话）
    ├─→ ASR_CHUNK → PC 中栏实时滚动
    ├─→ 风控检测（关键词 <50ms + LLM ~800ms）
    └─→ LLM 意图分析 → AI_SUGGESTION
              ↓
    App 底部卡片 + PC 右栏同步显示
```

**通话结束：**
```
挂机 → ASR flush（最多 3s）→ LLM 生成摘要（异步 ≤30s）
    ↓
App 弹出结果确认弹窗（预填 AI 判断）
员工一键确认 → 写库 → 更新 CRM 状态 → 更新排名数据
```

### 10.2 事后录音批量分析

```
PC 批量上传 / App 上传单条录音
    ↓ 文件校验（格式/大小/数量）
    ↓ 写入 Celery 任务队列
    ↓ Worker 消费 → ffmpeg 转 PCM（16kHz mono s16le）→ DashScope ASR
    ↓ LLM 结构化分析
    ↓ 结果写库，needs_review=true → 督导工作台生成待办
```

**文件规格**：

| 规格项 | 要求 |
|--------|------|
| 支持格式 | mp3 / m4a / amr / wav / aac / ogg |
| 单文件最大体积 | 100 MB |
| 单次批量上传上限 | 500 个文件 |
| 最短有效时长 | 5 秒（低于此时长标记为"无效录音"跳过 ASR）|
| 重复检测 | 同文件名 + 同大小的文件视为重复，提示跳过或覆盖 |

### 10.3 CRM 流转

```
案件创建 → 公海
    ↓ 自动分配 / 员工认领
  私海（员工独占）
    ↓ 每 30 分钟自动检查
  ┌────────────────────────────────────┐
  │ 超时未联系         → 回公海          │
  │ 连续失联 3 次      → 回公海          │
  │ 大额 + 失联 5 次   → 升级主管        │
  │ 欠费 ≥ 6月 + 失败  → 法务队列        │
  │ 失联 ≥ 7 次        → 上门工单        │
  │ 小额 + 90天无进展  → 自动关闭        │
  └────────────────────────────────────┘
  通知：WebSocket 实时推送（在线）+ 企微/钉钉（离线）
```

### 10.4 工单与法务转接

```
催收员通话中（或通话后）点击「建工单」
    ↓ 填写：问题类型 / 描述（自动带入 AI 摘要片段）/ **优先级**
    ↓ 工单进入工单处理员队列
    ↓ 工单处理员处理完成后系统通知催收员

催收员/督导 点「申请转法务」(reason 必填,7 个预设原因 + 「其他」需补充)
    ↓ 督导审批「是否转出」(不再选服务包) — 批准 / 驳回 / 上报 admin
    ↓ admin 审批(若上报)— 批准 / 驳回
    ↓ 状态变 approved_pending_legal,进入物业法务工作台「待法务接单」队列
    ↓ 物业法务接单 → 选服务包(律师函/调解/小额诉讼/完整代理)— 此时才看金额
    ↓ 创建 LegalConversionOrder + 状态 approved → 物业法务内部处理
    ↓(可选)升级到合作律所 → 平台 OPS 撮合 → 律所接单
    ↓ 状态变更通知管理员 / 原催收员 / 督导 / 法务
```

**v0.5.4 转法务三段式新流程要点**:

| 阶段 | 谁来做 | 看不看金额 | 看不看服务包 |
|---|---|---|---|
| 1. 提单子(申请) | 催收员(或物业 admin 直建) | ❌ | ❌ |
| 2. 审批(是否转出) | 督导(可上报 admin)/ admin | ❌ | ❌ |
| 3. 接单选包 | 物业法务 | ✅ | ✅ |
| 4. 撮合律所 | 平台 OPS / 服务商 | ✅ | ✅ |

**理由**:服务包是法务专业判断,跟金额绑定;让催收员/审批人决定不合理。催收员只填「为什么转」(预设 7 类),督导/admin 只判断「是否转出」,法务接单时再选合适的服务包。

**催收员申请理由 7 类(预设单选 + 「其他」需补充)**:
业主长期失联(>1 个月) / 业主反复拒绝沟通 / 大额欠费且账龄长 / 业主明确否认债务 /
已多次承诺但反复违约 / 走司法可能性高(业主有资产)/ 其他

**v1.6 — 工单优先级（4 档）**

| code | 标签 | UI 配色 | 触发场景 |
|---|---|---|---|
| `urgent_critical` | 很紧急 | 红 | 漏水/电梯故障/明火 等需立即响应 |
| `urgent` | 紧急 | 橙 | 业主已升级到管理处 / 多次催办 |
| `normal` | 一般 | 灰 | 默认值；常规反映 |
| `low` | 低 | 灰 | 信息记录 / 后续跟进 |

数据库层 CHECK 约束保证只接受这 4 个值；前端工单列表支持按 priority
过滤；新建工单时必填，详情页可修改。

### 10.5 标记承诺缴费(v0.5.6 结构化字段)

v0.5.6 之前,催收员「标记承诺缴费」只把案件 stage 改成 `promised` + 写一条自由文本备注;业主到底**承诺什么 / 承诺多少 / 何时缴**全部丢在 note 自由文本里,无法上报、无法追踪兑现、报表抓不到结构化数据。

v0.5.6 起新增 3 个结构化字段(`CollectionCase` 表,迁移 `24025_v056_promise_fields`):

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `promise_content` | VARCHAR(500) | ✅ | 承诺什么:6 个预设选项 + 可选自由文本补充 |
| `promise_due_at` | DATETIME(tz) | ✅ | 承诺缴费日期 — 复用 v1.6 已有字段(原用于到期提醒) |
| `promise_amount` | NUMERIC(12,2) | ❌ | 承诺金额(业主只口头承诺不报金额时可空) |

**6 个预设承诺内容**:全额缴清 / 先缴本金,违约金后续协商 / 先缴一半,剩余分期 / 分期 2 次(50%+50%) / 分期 3 次(每月 1/3) / 其他(必填自由文本)。

**前端 SSOT 组件**:`frontend/src/components/case/MarkPromiseModal.tsx`,供以下入口共用:
- 催收员工作台快捷操作 → 「✅ 标记承诺缴费」按钮
- 催收员/督导/admin 案件详情 → 跟进备注卡阶段下拉选「承诺缴费」时自动弹出

**API**:`PATCH /api/v1/agent/cases/{id}/stage`,当 `stage='promised'` 时接收 3 字段写入 case 行 + AuditLog payload;其他阶段切换不动 promise_* 字段(避免误清空历史承诺)。

**报表收益**:到期前 24 小时自动提醒回访(scan_and_notify_promise_expiring 已有,只是之前没结构化数据可用);后续兑现追踪可对账 `paid_at` vs `promise_due_at`。

### 10.6 工单创建入口统一(v0.5.6)

v0.5.6 之前,「创建工单」在 4 处入口有 3 套不同实现:

| 入口 | 旧实现 | 字段 |
|---|---|---|
| 催收员工作台 | `window.prompt` | 仅 description |
| 催收员案件详情 | 自写 Modal | 3 字段(type/priority/description) |
| 督导案件详情 | 共享 `WorkOrderCreateModal` | 3 字段 |
| 物业 admin 案件详情 | 共享 `WorkOrderCreateModal` | 3 字段 |

催收员工作台缺工单类型 + 优先级选择 → 一律 `case_followup + normal`(后端 422 风险);两套实现散落不易维护。

v0.5.6 起 **5 处统一使用** `frontend/src/components/admin/WorkOrderCreateModal.tsx`(SSOT)。组件 props 仅 `caseId + onClose + onSuccess`,POST `/workorders` 后端逻辑不变。

---

## 11. App-PC 联动技术方案

### 11.1 通信架构

| 通道 | 协议 | 用途 |
|------|------|------|
| 信令通道 | WebSocket (STOMP) | 会话事件、ASR 文本、AI 建议、风控告警、快捷操作指令 |
| 音频通道 | WebSocket 二进制 | App → 后端 PCM 音频帧（640字节/帧，20ms） |
| 会话状态 | Redis Hash TTL 4h | `call:session:{sessionId}`，多端共享 |

所有在线端订阅：`/topic/agent/{agentId}/session`，任意端发起通话，其余端自动感知。

### 11.2 消息类型

| 类型 | 方向 | Payload 要点 |
|------|------|-------------|
| DIAL_REQUEST | 后端→App | phone（脱敏展示用）, owner_id, case_id |
| CALL_STARTED | 后端→双端 | sessionId, ownerId, ownerName |
| CALL_ENDED | 后端→双端 | sessionId, duration |
| ASR_CHUNK | 后端→PC | speaker, text, isFinal, audioOffsetMs |
| AI_SUGGESTION | 后端→双端 | level, content, triggerText, actions[] |
| RISK_ALERT | 后端→双端 | level(1-3), category, detectedText |
| QUICK_ACTION | PC→后端 | actionType(SEND_QR/CREATE_WORKORDER/ESCALATE) |
| SUPERVISOR_TAKEOVER | 后端→App | 督导发起强制转接请求，App 弹出接受/拒绝浮层 |
| FORCE_LOGOUT | 后端→App/PC | 新设备登录踢出旧设备；payload: reason(OTHER_DEVICE_LOGIN), new_device_type |
| HEARTBEAT | 双端→后端 | 10s/次，15s 无响应标记离线 |

### 11.3 员工忙碌时的 DIAL_REQUEST 处理

**原则**：不打扰正在通话的员工，UI 层前置拦截，不依赖运行时判断。

```
PC 端显示员工状态（来自 Redis call:session）：
  · 空闲（IDLE）  → 「拨打」按钮可点击
  · 通话中（IN_CALL）→ 「拨打」按钮置灰，Tooltip：「该员工通话中，结束后可重新发起」

若因竞态条件 DIAL_REQUEST 已发出但员工刚进入通话：
  App 侧：检查当前状态，若 IN_CALL 则静默丢弃，不展示通知
  后端：返回 409 AGENT_BUSY，PC 提示「员工当前忙碌，已取消本次拨号请求」
```

**管理员/督导例外**：督导在 PC 端有「强制转接」权限，可向通话中的员工发送 SUPERVISOR_TAKEOVER 消息，App 弹出「主管请求转接」浮层，员工选择接受/拒绝。

### 11.4 说话人区分策略（Speaker Diarization）

手机通话为单声道录音，无法做传统说话人分离。MVP 采用**近/远场启发式推断**：

- DashScope paraformer-realtime-v2 能感知近场（麦克风直接采集，催收员）与远场（手机扬声器回传，业主）音量差异，自动标注 `speaker: "near" / "far"`
- 后端将 `near` 映射为 `agent`，`far` 映射为 `owner`；若 DashScope 无法区分，统一标记 `unknown`
- 转写结果按轮次存储（每个句子带 speaker 标签），PC 端实时对话区用不同气泡颜色区分
- **不引入自定义说话人分离模型**，接受约 15-20% 的误标率，督导复核时可手动修正

### 11.5 单设备在线限制

同一账号同一时刻只允许**一台 App 或一台 PC** 处于已认证状态：

```
新设备登录成功
    ↓ 后端检查 Redis active_session:{user_id}
    ├─ 无旧会话 → 正常登录，写入新 session
    └─ 有旧会话 → 向旧设备推送 FORCE_LOGOUT（附原因：OTHER_DEVICE_LOGIN）
                  旧设备 App/PC 弹出提示「您的账号已在其他设备登录」→ 返回登录页
                  新设备正常进入工作台
```

- App 和 PC 互相独立计算（一台 App + 一台 PC 可同时在线，用于 App-PC 联动场景）
- 同类型设备只允许一台（不能两台手机同时登录同一催收员账号）

### 11.6 网络中断处理

- **App 信令断线**：指数退避重连（1→2→4s），重连后发 SESSION_RESUME
- **App 音频断线**：本地环形缓冲 60s，重连后按 sequenceNo 顺序补传
- **PC 断线**：重连后拉 GET /api/sessions/active，自动恢复三栏工作台

### 11.7 PC 实时通话墙（v1.3，Sprint 14.2）

让主管/管理员/项目负责人在 PC 上集中观察全部坐席的当前通话情况，弥补 Android App 屏幕过小、坐席单兵作战时主管缺失全局视角的问题。

**触发链**

```
agent App 内点「拨打」
    ↓ POST /api/v1/calls/dial-start { case_id, device_id }
    ↓   - 决议 recording_mode (live/post) 并冻结 (PRD §20.1.1)
    ↓   - 软配额检查（剩余 ≥3 分钟才放行）
    ↓   - DB partial unique index 防同一坐席并发拨号 → 409
    ↓   - WS /ws/supervisor 广播 call.started 事件
PC 实时通话墙立即显示卡片（无需主管手动操作）
    ↓ agent App 30s 一次 POST /calls/{id}/heartbeat 保活
    ↓ 90s 无心跳 → 后台任务自动 status='aborted' + 广播 call.aborted
通话挂机：app 上报 → call.ended 广播 → 卡片消失
```

**PC 端页面 `/supervisor/live-wall`**

- 角色访问：supervisor / admin / project_manager_property
- 卡片信息：坐席名 / 案件号 / 业主名（已脱敏号码）/ 已通话时长 / recording_mode 标签 / 风控告警边框
- 卡片点击 → 跳现有 `/admin/workstation/:call_id` 实时跟单页（看实时转写 + AI + 风控时间线）
- WS /ws/supervisor 增加事件类型：`call.started` / `call.ended` / `call.aborted`
- 初次加载用 GET `/api/v1/supervisor/live-calls` 拉快照

**设计原则**

- **不弹窗骚扰**：默认仅常驻列表，避免主管被打断；后续 P2 加「钉住关注下属」+ toast 提示
- **强制 App 内入口**：绕开 App 直接系统拨号 → 不调用 dial-start → PC 不显示，事后录音不上传（保护坐席私人电话隐私）
- **故障容错**：dial-start 失败不阻断本地拨号，PC 端就不显示而已（降级容错）

**已知部署约束**

- WebSocket session 状态当前为单进程内 dict（`ws_calls.py:_sessions`），prod 升 `--workers > 1` 前必须改造为 Redis pub/sub，否则同 call_id 跨 worker 时事件可能丢失。

---

## 12. 风控方案

### 12.1 检测链路

```
ASR 文本（含 speaker: agent/customer/unknown）
  → 关键词引擎（Aho-Corasick，<50ms，speaker 路由匹配）
       speaker=customer → 仅匹配 owner_* 词典
       speaker=agent    → 仅匹配 agent_* 词典
       speaker=unknown  → 跳过（保守策略，避免误打断）
  → 命中时 + 每 5 句话 → LLM 情绪分析（~800ms）
  → 风控事件聚合 → 按触发源分级干预
```

### 12.2 三级干预

| 级别 | 触发 | 适用场景 | App 行为 | PC 催收员端 | 督导端 |
|------|------|---------|----------|-------------|--------|
| **L1 提示** | 低风险词命中 | owner_abuse 或 agent_minor_misconduct | 黄色 Toast + 普通震动 | 右栏黄字提示 | 仅记录，不告警 |
| **L2 警告（业主侧）** | owner_threat 命中 或 LLM 业主激烈施压 | 业主威胁/投诉/法律施压 | 顶部红色 Banner + 强震动（**不阻塞、不静音**） | 橙色弹窗 | /ws/supervisor 实时告警 |
| **L2 警告（催收员侧）** | agent_violation 命中 或 LLM 催收员明确违规 | 催收员辱骂/威胁业主/违法暗示 | **全屏阻塞 Modal + 自动静音麦克风** + 强震动；点"知道了"才解除静音 | 橙色弹窗 + 标红催收员姓名 | /ws/supervisor 实时告警 |
| **L3 强制挂断** | LLM risk=3 或 L2-催收员侧被忽略 60s | 严重违规未纠正 | `call.disconnect()` | 自动标注留证 | 完整风控日志 |

**L3 开关策略**：L3 自动挂断**默认关闭**，需管理员在「系统配置 → 风控设置」中手动启用。开关存储在租户级配置表，不影响 L1/L2。未启用时 L3 触发条件满足后降级为 L2-催收员侧 + 督导强通知。

**核心设计原则**：
- 阻塞 + 静音麦克风**只针对催收员违规说话**（agent_violation），保护其在业主激烈施压时仍能正常应对
- 业主侧违规（owner_threat/owner_abuse）系统**不打断催收员通话**，由催收员自行决定是否挂断
- L1 同一行为（黄 Toast + 普通震动）出现两种语义：业主辱骂催收员→提醒催收员注意应对；催收员不当→提醒话术规范

### 12.3 关键词分类

按"说话人 + 行为性质"分四类，每条关键词关联 `speaker` 与 `level` 字段：

| 分类 | speaker | level | 词例 | 干预 |
|------|---------|-------|------|------|
| **owner_abuse** 业主辱骂 | customer | L1 | 你妈 / 滚 / 傻逼 / 神经病 / 等人身攻击 | 提示催收员 |
| **owner_threat** 业主威胁 | customer | L2 | 投诉 / 12345 / 上法院 / 媒体 / 律师 / 曝光 | 红 Banner + 督导告警 |
| **agent_violation** 催收员违规 | agent | L2 | **agent_insult**：辱骂业主词（与 owner_abuse 同源）；**agent_threat**：看我怎么收拾你 / 让你好看 / 去你单位 / 曝光你；**agent_illegal**：我打你 / 把你身份证发出去 / 等违法暗示 | **阻塞 Modal + 静音麦克风** + 督导告警 |
| **agent_minor_misconduct** 催收员不当 | agent | L1 | 承诺减免 / 随便你 / 爱交不交 | 仅记录 + 催收员端 Toast 提醒话术 |

**关键说明**：
- 原列表中"承诺减免费用"从 L2 员工违规降级到 L1 不当——减免可协商，不构成法律意义违规
- agent_violation 聚焦"刚性红线"（辱骂/威胁/违法暗示），误检成本可承受、阻塞正当性强
- 关键词支持租户自定义（PRD §18.5）：管理员可为本租户启用/新增词，不能禁用平台预置词

### 12.4 留证机制

风控事件记录 `audio_offset_ms`，通话结束后自动切片（前后各 30s），督导点击事件可直接跳转录音对应时间点回放。

---

## 13. CRM 公海/私海策略

> **MVP 与 v1.1 边界**：私海规则、入公海条件、升级路径在 MVP 中已实现，逻辑由后端强制执行；**自动流转规则引擎（每 30 分钟定时任务）推迟到 v1.1**，MVP 阶段由管理员手动分配和流转。

### 13.1 私海规则

| 欠费等级 | 金额 | 独占时限 | 单人上限 |
|----------|------|----------|---------|
| T1 | < ¥1,000 | 48h | 30 条 |
| T2 | ¥1,000–5,000 | 72h | 20 条 |
| T3 | > ¥5,000 | 24h | 10 条 |
| 外部兼职合计 | — | — | 10 条 |

优先级评分 = 欠费金额×0.4 + 欠费月数×0.3 + 人工标记×0.3

### 13.2 入公海条件

- 独占超时且拨打次数为 0
- 连续失联 ≥ 3 次
- 员工主动释放
- 员工账号停用/到期

### 13.3 自动流转规则（每 30 分钟）

| 条件 | 动作 |
|------|------|
| 大额(>¥10k) + 拨打≥3 + 失联≥3 | 升级主管 |
| 欠费≥6月 + 拨打≥10次 | 进法务队列 |
| 失联≥7次 | 生成上门工单 |
| 小额(<¥200) + 拨打≥5 + 90天无进展 | 标记「低优先级/暂停」，回公海底部队列，不自动关闭（关闭需管理员手动确认）|

### 13.4 升级路径(v0.5.4 简化为一级)

```
催收员 → 督导(接案后自己负责到底)
                ↓
       重大事项不走案件 transfer,改走审批单:
         · 大额减免 → DiscountOffer → 督导审批 → 可上报 admin
         · 转法务   → LegalConversionRequest → 督导审批 → 可上报 admin → 法务接单选包
```

**v0.5.4 关键变化**:
- 取消「督导→admin」案件 transfer:督导一旦接案就自己负责到底,不再把案件本身上交 admin
- 重大事项的把关改用「**审批单 + 上报机制**」(更细粒度,且可审计每一单的决策路径)
- 督导有「上报 admin」按钮(单据级,不是案件级),把超出自己决断范围的单子转 admin 决

### 13.5 联系频次自动控制

同一业主的联系次数在 CRM 层强制管控，防止被投诉骚扰：

| 规则 | 默认值 | 管理员可调范围 |
|------|--------|-------------|
| 同一业主每自然月最多联系次数 | 6 次 | 3–10 次 |
| 同一业主每日最多联系次数 | 2 次 | 1–3 次 |
| 两次联系最短间隔 | 24 小时 | 12–72 小时 |

**执行机制**：
- 超频时「拨打」按钮置灰，显示「本月已联系 N 次，下次可联系日期：MM-DD」
- 督导/管理员有「豁免联系」权限（需填写原因，记入审计日志）
- 合规月报自动统计超频豁免次数，作为合规指标

### 13.6 外呼号码管理（v1.1）

防止催收员个人号码被业主投诉后封号影响正常业务：

**号码池机制**：
- 管理员维护一批外呼号码（可以是 SIM 卡手机号或 VOIP 虚拟号）
- 系统按轮询或负载均衡策略自动分配外呼号
- 单个号码累计投诉 N 次后自动下线并告警管理员

**显号策略**（v1.1）：
- 展示给业主的主叫号码可配置为公司统一号码（需运营商支持）
- 催收员 App 端拨出使用绑定的外呼号，不暴露个人手机号

> **MVP 阶段**：号码管理不做，催收员使用个人手机号外呼；v1.1 引入号码池。

### 13.7 抢单与释放（v1.6.9）

**抢单（claim）**：催收员在「我的案件」页 → 切到「公海池」tab，点行内「抢单」按钮主动认领，无需等管理员分配。

| 端点 | 角色 | 说明 |
|---|---|---|
| `GET /agent/me/pool-quota` | agent_internal/external | 返回 `{held_open, claim_max, can_claim_more, remaining}` 用于前端进度条与按钮置灰 |
| `POST /agent/cases/{id}/claim` | agent_internal/external | 校验持有上限 + 案件仍属 `pool_type=public` AND `assigned_to=null`；成功后写 audit `case.claimed` |
| `POST /agent/cases/{id}/release` | agent_internal/external | 仅本人持有的未结案（stage NOT IN paid/closed）可放回公海；写 audit `case.released` |

**持有上限配额**（`tenant_settings.public_pool_claim_max`）：默认 50，CHECK 1-1000。达到上限后 `claim` 返回 409 `ERR_CLAIM_LIMIT`。

**与 §13.1 私海上限的区别**：§13.1 的 30/20/10 是按欠费等级分别计的「同时持有该等级案件数」上限（业务侧软规则）；§13.7 的 `public_pool_claim_max` 是按用户的「未结案案件总数」（不区分等级）的硬性配额，由后端在 claim 时强制（防止"快手"催收员把整个公海抢空导致团队负载不均）。两者并行生效。

> **设计思考**：原方案是只允许管理员分配，但实测发现物业体量小、管理员手动分配成为瓶颈；催收员之间能力差异大，"快手"应该被允许多接。引入 claim + 上限组合既释放了催收员主动性，又通过配额避免抢单失控（v1.6.9 决策详见 §22.1）。

---

## 14. 支付功能

### MVP：缴费链接 + H5 静态账单页（v2.2 已交付）

**核心闭环**：物业管理员按项目配置收款信息 → 催收人员点「发送缴费链接」生成业主专属 token → 弹窗展示二维码 + 支付明细 → 业主扫码/点链接打开公开 H5 账单页，按页面展示的线下方式缴费。

**MVP 不接在线支付**；H5 落地页为静态账单（无支付按钮），公证提存 + 在线通道留到 v1.1。

#### 项目级收款配置（按项目，物业管理员配）

`Project` 表新增 5 字段，物业管理员在项目编辑页录入：

| 字段 | 类型 | 说明 |
|------|------|------|
| `payment_mode` | String(16) | `property_self`（物业自收，MVP）/ `notary_escrow`（公证提存，v1.1 预留），默认 `property_self` |
| `payee_name` | Text | 收款户名（如「××物业管理有限公司」） |
| `payee_account` | Text | 收款账户，自由文本（银行 + 账号 / 对公账户） |
| `payee_qr_object_key` | Text | 收款码图（微信/支付宝收款码）MinIO key（v2.2 字段已就位，前端上传控件待补）|
| `payment_instructions` | Text | 线下缴费说明（缴费时间、服务中心地址、转账备注等） |

> 一个物业公司管多个项目，各项目可独立配收款账户。

#### token 持久化（`payment_link` 表）

每次发送生成一条新行：`token`(unique) / `case_id` / `tenant_id` / `project_id` / `created_by_user_id` / `payment_mode`（发送时快照） / `expires_at`（默认 +7 天）/ `created_at` / `updated_at`。token 不复用，旧 token 到期自然失效。

#### 支付明细构成 —— 应缴 − 已减免 = 应支付

业主弹窗 + H5 页都展示同一份明细：

```
物业费本金          ¥ principal_amount
违约金 / 滞纳金     ¥ late_fee_amount
─────────────────────────
应缴合计            ¥ amount_owed
已减免            - ¥ waived            ← waived = 0 时该行隐藏
═════════════════════════
应支付              ¥ payable
```

**减免联动规则**：`waived` 来自案件**已审批通过（status='approved'）且未过期**的 `DiscountOffer`（多条取 `approved_at` 最新一条）；pending 减免**不抵扣**。`payable = approved_offer.proposed_amount`；无有效 offer 时 `payable = amount_owed`。

#### H5 实时计算

模式 A（物业自收，MVP）下 H5 页**每次打开实时跑 `compute_payable`**，不冻结发送时金额 —— 催收员承诺的减免后续审批通过，业主刷新链接即见降后金额，无需重发。

#### 待审批减免非阻断提醒

发送时若该案件有 `status ∈ (pending_supervisor, pending_admin)` 的减免，**照常发送**，仅在弹窗顶部加提示：「⚠ 该案件有待审批减免，当前链接金额按已审批结果计算；减免审批通过后业主刷新链接即见更新。」

#### 发送方角色(v0.5.4)

三类角色都可发送缴费链接,弹窗 UI 同源(`PaymentLinkQrModal`),展示明细 + 二维码 + 短链:

| 角色 | 端点 | 范围 |
|---|---|---|
| 内勤/外部催收员 | `POST /api/v1/agent/cases/{id}/send-payment-link` | 仅 `assigned_to == 自己` 的案件(`require_roles("agent")` + 自有 case 校验)|
| 物业 admin / 督导 | `POST /api/v1/admin/cases/{id}/send-payment-link` | 本租户任意案件(`require_tenant_roles("admin","supervisor")`)|

#### 公开端点 + 公开页（业主侧，免登录）

| 端点 | 说明 |
|------|------|
| `GET /api/v1/public/payment/{token}` | 无鉴权；404 unknown / 410 expired / 200 valid；**不返回业主手机号**（PRD §6 隐私要求） |
| `/pay/:token`（前端） | 业主扫码/点链接打开的 H5 账单页，渲染明细 + 项目 payee 信息（收款户名/账号/缴费说明/可选收款码图） |

业主侧 H5 渲染版式：

```
┌──────────────────────────────────────┐
│   {payee_name}                       │
│   您好，[张三]，房号 [5-203]           │
│                                      │
│   ┌────────────────────────────────┐ │
│   │  物业费本金     ¥ 3,000.00     │ │
│   │  违约金/滞纳金   ¥   200.00     │ │
│   │  应缴合计        ¥ 3,200.00     │ │
│   │  已减免        - ¥   200.00     │ │
│   │  应支付          ¥ 3,000.00     │ │
│   └────────────────────────────────┘ │
│                                      │
│   缴费方式：{payment_instructions}    │
│   收款账户：{payee_account}           │
│   收款户名：{payee_name}              │
│   [可选：收款码图]                     │
│                                      │
│   ── v1.1 上线后可在此直接扫码支付 ── │
└──────────────────────────────────────┘
```

#### 隐私与安全

- 业主 H5 页**不显示手机号**（防止扫码/转发链接的人通过页面提取业主信息）
- token 7 天有效，过期返回 410
- 公开端点无鉴权但凭 token 检索；token 32 字符 base64url（≈190 bit 熵，碰撞概率可忽略）

### v1.1：在线支付接入

在线支付是**共用的基础设施**，直接付款和公证提存都通过同一套支付通道完成，区别仅在于资金流向。

#### 支付通道

- 微信/支付宝服务商模式（sub_mch）：平台作为服务商，每个租户注册子商户，收款直接到子商户账号
- 收款渠道：微信扫码/支付宝扫码/H5 跳转

#### 两种付款模式

```
业主打开支付页面（扫二维码 / 点链接）
    ↓
选择付款方式：
  ┌─────────────────────────────────────┐
  │  💳 直接付款       公证提存付款 📋  │
  │  款项直达物业账户   款项存入公证账户  │
  └─────────────────────────────────────┘
```

**模式 A：直接付款**
```
扫码 → 选择直接付款 → 微信/支付宝完成支付
    ↓
款项进入租户子商户账号（物业公司直收）
系统更新案件状态 → 通知催收员 → CRM 标记已缴费
```

**模式 B：公证提存付款**
```
扫码 → 选择公证提存 → 微信/支付宝完成支付
    ↓
款项进入平台公证提存账户（与公证处合作，资金隔离托管）
系统自动生成《提存证书》PDF，推送给业主和物业公司
    ↓
物业公司确认无异议 → 申请划出 → 正常到账
物业公司有异议    → 公证调解 → 公证处裁定后划付
```

公证提存依据《民法典》第 570 条：债务提存视为履行债务，业主获得证书后催收即应停止，提升付款意愿。

#### 各方价值

| 受益方 | 直接付款 | 公证提存 |
|--------|---------|---------|
| 业主 | 快捷便利 | 有法律凭证，不怕被继续追诉 |
| 物业公司 | 即时到账 | 减少坏账纠纷，提存记录可用于法务证据 |
| 平台 | 收取通道服务费 | 资金过手，支撑按回款金额抽佣；提存服务额外收费 |

#### 数据模型

```sql
CREATE TABLE payment_record (
    id                  BIGSERIAL PRIMARY KEY,
    tenant_id           INT NOT NULL,
    case_id             BIGINT NOT NULL,
    amount              NUMERIC(10,2) NOT NULL,
    payment_type        VARCHAR(20),    -- direct / escrow
    channel             VARCHAR(20),    -- wechat / alipay
    status              VARCHAR(20),    -- pending / paid / deposited / released / disputed / refunded
    escrow_cert_url     TEXT,           -- 提存证书 PDF（escrow 模式）
    platform_fee        NUMERIC(10,2),
    net_amount          NUMERIC(10,2),
    paid_at             TIMESTAMPTZ,
    released_at         TIMESTAMPTZ,
    settlement_id       INT
);
```

**前置条件**：需申请微信/支付宝服务商资质；公证提存模式需与持有提存资质的公证处或机构签署合作协议。

---

## 15. 服务商结算体系

### 15.1 结算相关角色

| 角色 | 结算视角 |
|------|----------|
| 物业公司管理员 | 查看应付给各服务商的结算单，审核确认，标记付款 |
| 服务商管理员 | 查看各客户应收账款，查看成员工作量明细，导出账单 |
| 平台超管 | 查看全平台交易流水，监控结算健康度 |

### 15.2 结算标准配置

每份**服务商↔租户合约**独立配置结算规则，支持多种计费模式组合：

**兼职催收员计费方式（可选其一或组合）：**

| 计费方式 | 说明 | 示例 |
|----------|------|------|
| 按有效通话量 | 通话时长 > 30s 算有效，单价计费 | ¥2/通 |
| 按转化量 | 业主承诺缴费或已缴费，单价计费 | ¥15/件 |
| 按回款提成 | 实际到账金额的百分比 | 5% |
| 组合模式 | 底薪（按通话量）+ 奖励（按回款提成）| ¥1/通 + 3% |

**法务服务计费方式：**

| 计费方式 | 说明 | 示例 |
|----------|------|------|
| 月固定服务费 | 不管案件量，固定月费 | ¥3,000/月 |
| 按案件量 | 每个进入法务阶段的案件计费 | ¥200/件 |
| 按胜诉/回款提成 | 实际回款的百分比 | 8% |

**结算周期配置：**
- 月结（最常用）
- 半月结
- 按案件实时结算（适合纯提成模式）

### 15.3 结算单生命周期

```
结算周期结束（如月末最后一天）
        ↓
系统自动生成结算单草稿（status: DRAFT）
按合约规则汇总：通话量 × 单价 + 转化量 × 单价 + 回款额 × 比例
        ↓
物业公司管理员收到通知 → 进入「结算管理」审核
可查看每条明细（每通电话/每个案件/每笔回款）
        ↓
管理员确认无误 → [确认结算]（status: CONFIRMED）
        ↓ 服务商收到确认通知
服务商管理员查看 → 核对无误 → [确认收款信息]
        ↓
线下转账 → 管理员上传付款凭证 → [标记已付款]（status: PAID）
        ↓
结算单归档，计入双方账单历史
```

**异议处理：**
```
服务商对结算单有异议 → 点击[申请复核] → 填写异议原因
        ↓
物业公司管理员收到通知 → 查看具体明细 → 协商修正
        ↓
双方确认 → 重新生成修正结算单 → 走正常确认流程
```

### 15.4 结算报表内容

**物业公司管理员看到（应付报表）：**

```
结算管理
├── 本月待确认结算单
│     ├── 兴华律所       ¥4,200   [查看明细] [确认]
│     └── 聚英兼职团队   ¥8,640   [查看明细] [确认]
│
├── 历史结算记录（可筛选服务商/时间段/状态）
│     月份     服务商        金额      状态
│     2026-03  兴华律所     ¥3,800   已付款
│     2026-03  聚英团队     ¥7,200   已付款
│
└── 应付汇总图表
      月度应付趋势 / 按服务商占比
```

**结算单明细（展开查看）：**

```
聚英兼职团队  2026年4月  结算明细

计费规则：有效通话 ¥2/通 + 转化 ¥15/件 + 回款 3%

成员明细：
┌──────┬───────┬───────┬───────┬────────┬────────┐
│成员   │有效通话│转化件数 │回款金额 │小计     │备注    │
├──────┼───────┼───────┼───────┼────────┼────────┤
│张某   │  156  │  18   │¥32,000│¥4,272  │        │
│陈某   │   98  │  11   │¥18,500│¥1,911  │        │
├──────┼───────┼───────┼───────┼────────┼────────┤
│合计   │  254  │  29   │¥50,500│¥6,183  │        │
└──────┴───────┴───────┴───────┴────────┴────────┘

[下载 Excel 明细]  [下载 PDF 账单]
```

**服务商管理员看到（应收报表）：**

```
收益概览
├── 本月应收
│     XX 物业  ¥6,183   待确认
│     YY 物业  ¥4,210   已确认，待付款
│     合计     ¥10,393
│
├── 团队成员收益排名（本月）
│     张某   ¥4,272 （XX物业¥2,100 + YY物业¥2,172）
│     陈某   ¥1,911
│
├── 历史回款记录（可筛选客户/成员/时间）
│
└── 应收趋势图表（按月/按客户）
```

### 15.5 平台超管结算视角

```
全平台结算概览
├── 本月结算金额（各租户↔服务商）
├── 结算完成率（已付款/总应付）
├── 逾期未结算告警（超过 30 天未付款）
└── 平台服务费收入（按租户订阅套餐）
```

### 15.6 催收员绩效积分与个人佣金

> 本节解决「物业公司/服务商 → 催收员个人」的绩效激励，与 15.1-15.5 的「平台/物业公司 → 服务商」结算独立分层。

**绩效积分规则（租户/服务商管理员可配置）**：

| 行为 | 默认积分 |
|------|---------|
| 完成一次有效通话（时长>30s）| +1 分 |
| 业主承诺缴费 | +5 分 |
| 业主实际缴费（直付确认）| +20 分 |
| 业主公证提存付款 | +15 分 |
| 督导标注"优质通话" | +3 分 |
| 风控 L2 触发（员工违规）| -10 分 |

**佣金计算**（服务商内部使用，物业公司内部员工参考）：
```
个人月度佣金 = Σ（案件回款金额 × 佣金比例）
             + 绩效积分奖金（超过阈值后按梯度发放）
             - 违规扣款
```

- 佣金比例、积分奖金梯度由管理员在「结算规则」中单独配置（每人可不同）
- 月末自动生成**个人收益单**（只有本人和管理员可见）
- 服务商管理员在确认结算单时，可查看每位成员的个人收益明细，用于核算内部薪酬

**数据模型补充**：
```sql
CREATE TABLE performance_record (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       INT NOT NULL,
    user_id         INT NOT NULL,
    period_month    DATE NOT NULL,          -- 统计月份（当月1日）
    total_calls     INT DEFAULT 0,
    effective_calls INT DEFAULT 0,
    promises        INT DEFAULT 0,
    conversions     INT DEFAULT 0,
    total_amount    NUMERIC(10,2) DEFAULT 0, -- 促成回款总额
    points          INT DEFAULT 0,
    commission      NUMERIC(10,2) DEFAULT 0,
    deductions      NUMERIC(10,2) DEFAULT 0,
    net_income      NUMERIC(10,2) DEFAULT 0
);
```

### 15.7 项目级佣金率（创建时按经营模式区分，v2.2）

`Project` 表新增两个佣金率字段：`internal_agent_commission_rate`（内勤）+ `provider_agent_commission_rate`（服务商）。物业管理员**创建项目时**按经营模式选择填入哪个：

| 经营模式 | 录入字段 | 说明 |
|---------|--------|------|
| 物业自办 | `internal_agent_commission_rate` | 内勤催收员佣金率 |
| 外包给服务商 | `provider_agent_commission_rate` | 服务商坐席佣金率**初始值** |

**职责边界**：
- 物业 admin 仅能在**创建时**写 `provider_agent_commission_rate` 初始值；`PATCH /admin/projects/{id}` 不含此字段，避免事后单方面调降
- 服务商可在自家 `PATCH /provider/projects/{id}/commission-rate` 端点覆盖该值
- 两字段均 `NUMERIC(6,4)`，NULL 时回退系统默认 0.05（5%）

---

## 16. 数据模型概要

### 平台与租户层

| 实体 | 说明 |
|------|------|
| Tenant | 物业公司主体，所有数据的隔离边界，含订阅套餐 |
| ServiceProvider | 服务商主体（律所/兼职团队），类型：legal/collection/both |
| ProviderTenantContract | 服务商↔租户合约：签约日期、到期日、授权服务类型、结算周期 |
| User | 全局唯一账号（跨租户共享） |
| UserTenantMembership | 用户↔租户多对多：role、source_type(INTERNAL/PROVIDER)、provider_id、quota、expire_at、access_hours |
| PlatformOpsAssignment | 平台运营员客户分配：ops_user_id、entity_type(tenant/provider)、entity_id、assigned_at、notes；运营员只可操作自己名下分配的客户 |

### 催收业务层

| 实体 | 说明 |
|------|------|
| OwnerProfile | 业主档案：姓名、房号、手机（AES-256加密）、欠费金额、标签 |
| CollectionCase | 催收案件：公海/私海状态、流转阶段、优先级评分、分配员工 |
| CaseAssignmentHistory | 案件分配/流转历史，每次变更原因 |
| CallRecord | 一次通话：时长、发起方式(app/pc)、结果标签、情绪标签、风控标记 |
| Transcript | ASR 输出，按说话人分轮存储，含时间戳，手机号已脱敏 |
| AnalysisResult | LLM 输出：摘要、关键片段、跟进建议、Prompt 版本号 |
| RiskEvent | 风控事件：级别、类别、触发文本、audio_offset_ms、干预动作 |
| RiskKeyword | 风控关键词词典：tenant_id (NULL=平台预置)、category、speaker(agent/customer)、level、keyword、is_active；支持租户自定义词，含审计字段 created_by/created_at |
| WorkOrder | 工单：类型、描述、状态、处理人、关联通话 |
| LegalCase | 法务案件：进展状态、文档列表、关联原始催收案件 |
| ReviewRecord | 督导复核记录，AI 判断 vs 人工判断对比，用于模型优化 |
| ScriptTemplate | 话术模板，按异议类型分类，含使用统计 |
| SuggestionFeedback | 话术推送反馈：催收员采用/忽略、督导标注、业务结果推断信号 |
| PaymentLink | 业主缴费链接 token 持久化（v2.2 取代 PaymentQRRecord）：token (unique)、case_id、project_id、created_by_user_id、payment_mode、expires_at（默认 +7 天）；业主凭 token 经公开端点 `/api/v1/public/payment/{token}` 打开 H5 账单页，详见 §14 |
| DiscountOffer | 减免/分期申请：offer_type、original_amount→proposed_amount、status（pending_supervisor/pending_admin/approved/rejected/executed/expired）、approver_role_required、approved_at、**escalated_to_admin_at**（v0.5.4 督导上报 admin 的时间戳）、expires_at（7 天有效）、audit_trail |
| LegalConversionRequest | 转法务申请单（v1.6.8 + v0.5.4）：requester_user_id、reason（NOT NULL,预设原因 + 「其他」补充）、status（pending→approved_pending_legal→approved 或 pending_admin / rejected / cancelled）、reviewer_*、**escalated_to_admin_at**（督导上报）、related_order_id（法务接单后回填）|
| LegalConversionOrder | 法务转化订单：case_id、package_id、price_quoted、status、assigned_law_firm、assigned_lawyer_name、internal_close_reason / internal_closed_at（物业法务内部处理结果）— 法务接单 /legal-finalize 时由 LegalConversionRequest 衍生 |
| LegalServicePackage | 法务服务包目录：lawyer_letter/mediation/small_claims/full_agency 4 种,price + platform_fee_rate;平台级 + 租户可定制 |
| PaymentRecord | 业主在线付款记录：payment_type(direct/escrow)、channel、status、escrow_cert_url、platform_fee（v1.1）|
| BlockchainProof | 区块链存证回执：data_id、data_type、data_hash、tx_hash、chain、block_height（v1.1）|

**v0.5.4 timeline event_type 新增**(`services/case_timeline.py` 聚合自 `AuditLog`):
- `case.reassigned` — 督导重新分配
- `case.supervisor_remind_callback` — 督导催回访
- `case.supervisor_urge` — 督导催办
- `case.supervisor_intervene` — 督导介入处理

每动作除 timeline 外,还推送 `Notification(event_type=supervisor_action)` 给原催收员(reassign 时为新+原催收员两条)。

### 结算层

| 实体 | 说明 |
|------|------|
| SettlementRule | 结算规则：关联合约、计费方式（通话量/转化量/回款提成/组合）、单价/比例、结算周期 |
| SettlementStatement | 结算单：关联合约+周期、状态(DRAFT/CONFIRMED/PAID/DISPUTED)、总金额 |
| SettlementLineItem | 结算明细行：关联成员、计费依据(call_id/case_id)、数量、单价、小计 |
| SettlementPaymentRecord | 结算付款凭证：结算单ID、金额、时间、凭证图片URL、操作人（区别于业主付款的 PaymentRecord）|
| DisputeRecord | 结算异议记录：关联结算单、异议原因、处理状态、解决结果 |

### 16.X v0.6.0 新增字段 / 新表汇总

5 个 alembic 迁移(24027v060a → 24031v060e)交付,字段名为**最终生产实际名**(与本节其他段一致):

```
表:settlement_statement(改)
  + billing_method VARCHAR(32) NULL — 计费方式枚举
    CHECK 约束 ck_settlement_billing_method
    枚举:monthly_fee(月度套餐费)/ per_case(按案件计费)/
         percent_of_recovered(按回款比例分成)
    迁移:24027v060a

表:collection_case(改)
  + shadow_supervisor_id BIGINT FK user_account.id NULL
    — 督导陪同监听标记;非 NULL = 该案件在实时通话墙高亮,催收员拨号时
      督导自动收通知,可监听或强制接管(B.2 介入处理选项 ②)
  + close_reason TEXT NULL
    — 「直接结案/标坏账」必填原因(B.2 介入处理选项 ③);
      stage='pending_close' 时设置,等物业管理员二审
    迁移:24028v060b

表:risk_event(改)
  + handle_status VARCHAR(32) NULL — 督导处置状态枚举
    CHECK 约束 ck_risk_event_handle_status
    枚举:resolved(已处置)/ escalated(升级督导队列)/
         transferred_training(转培训案例)/ transferred_legal(转法务)
    迁移:24029v060c

  注:disposition_note / disposition_by / disposition_at(Sprint 9.4 已有)
      复用为「处理结果说明」+ 处置人 + 处置时间。

表:script_template(改)
  + ai_score NUMERIC(5,2) NULL — AI 评分 0-100
  + ai_score_updated_at TIMESTAMPTZ NULL — 最近重算时间
  + ai_score_sample_count INTEGER NULL — 样本数;<5 不算分,
    5-9 UI 提示「样本不足」⚠
    迁移:24030v060d
    算法:见 §22.9

表:training_case(新)— 培训案例库,替代纯 mock
  - id BIGINT PK AUTOINCREMENT
  - tenant_id BIGINT FK CASCADE
  - title VARCHAR(256) / category VARCHAR(32) / scenario TEXT / lesson TEXT
  - raw_call_id BIGINT FK SET NULL — 来源通话
  - raw_risk_event_id BIGINT FK SET NULL — 从风险事件转入时的源 event
  - source VARCHAR(16) DEFAULT 'manual' — auto(自动 curate)/ manual(督导手工)
  - created_by BIGINT FK user_account.id NULL
  - rating SMALLINT 0-5 / views INTEGER DEFAULT 0
  - created_at / updated_at(TimestampMixin)
  - CHECK 约束:
    - category IN ('negotiate','escalate','objection','investigate')
    - source IN ('auto','manual')
    - rating BETWEEN 0 AND 5
  - INDEX:tenant_id + created_at(列表分页)
    迁移:24031v060e
```

**关联端点(本波新加)**:
- `GET /admin/legal-conversion-orders/{order_id}/attestations` — 法务转化订单页区块链存证 section(走 LegalConversionOrder → CollectionCase → LegalCase → BlockchainAttestation 链)
- `POST /supervisor/cases/{id}/transfer-legal` — 督导直接移交法务(§4.4 路径 B)
- `POST /supervisor/escalated/{id}/mark-shadow-listening` — 标记陪同监听
- `POST /supervisor/escalated/{id}/close-as-uncollectible` — 直接结案审批
- `POST /supervisor/cases/{id}/release-to-pool` — 释放回公海
- 扩 `PATCH /supervisor/risk-events/{id}` — 支持 handle_status 同步写
- 培训库 CRUD:`GET/POST/PATCH/DELETE /supervisor/training-cases` + `POST /{id}/view`
- `POST /admin/scripts/recompute-ai-scores` — 手动触发 AI 评分重算
- `GET /agent/me/by-project` — 催收员按项目维度统计
- `GET /agent/me/reminders/synthetic` — 3 类软提醒整合
- 扩 `GET /users/me/notifications` — event_type 多值过滤
- `GET /pm/dashboard/alerts` — PM 5 类运营提醒

---

## 17. 账号注册与开通策略

### 17.1 设计原则

有证慧催涉及通话录音、业主隐私和财务数据，**不采用纯自助注册制**，采用**三级混合制**：

- 企业账号（租户）由平台销售驱动，签约后后台开通
- 服务商独立申请，平台审核资质后开通
- 企业内部成员由管理员直接创建
- 外部兼职必须通过邀请链接进入，不允许自主注册

| 账号类型 | 创建方式 | 操作方 | 理由 |
|---------|---------|-------|------|
| 物业公司（租户） | 后台分配（可配在线申请表单） | 平台运营团队 | 合同驱动，数据敏感需人工确认 |
| 服务商 | 申请制 + 平台审核 | 服务商自主申请 | 独立主体，需资质核验，可服务多家租户 |
| 内部员工 | 管理员直接创建 | 物业公司/服务商管理员 | 内部人员，最简流程，短信通知 |
| 外部兼职催收员 | 邀请链接（限时限次） | 物业公司/服务商管理员 | 受控入口，防止任意注册带走数据 |

---

### 17.2 物业公司账号开通流程

```
线上申请（官网填写试用申请表）或线下商务签约
        ↓
平台运营后台创建租户
  填写：公司名称 / 统一社会信用代码 / 管理员姓名+手机 /
        订阅套餐 / 账号有效期 / 最大用户数
        ↓
系统自动创建管理员账号，发送短信通知：
「您的有证慧催账号已开通，初始密码：XXXXXX，请及时登录修改密码」
        ↓
管理员首次登录 → 强制修改密码 → 完善公司信息 → 进入系统
```

**试用机制（降低销售门槛）：**
- 官网提供「申请试用」表单，填写公司名称/联系人/手机
- 平台运营 1 个工作日内审核，通过后开通 14 天试用账号
- 试用期限制：最多 5 个用户、50 条案件、不含服务商功能
- 试用到期后签合同升级正式账号

---

### 17.3 服务商账号申请流程

```
服务商在官网/App 点击「服务商入驻」
        ↓
填写基本信息：
  · 服务商名称（律所/团队名称）
  · 服务类型：法务 / 催收 / 两者兼有
  · 营业执照（律所需上传律师事务所执照）
  · 管理员姓名 + 手机号
        ↓
平台运营审核（1-3 个工作日）
  审核要点：营业执照真实性 / 服务类型匹配
        ↓
审核通过 → 开通服务商管理员账号，短信通知
审核拒绝 → 短信告知原因，可补充材料重新申请
        ↓
服务商管理员登录 → 添加团队成员 → 等待/主动申请与物业公司合作
```

**服务商与物业公司绑定（双向发起）：**

```
路径 A：物业公司主动邀请
  管理员 → 合作伙伴 → 搜索服务商名称 → 发出合作邀请
      ↓ 服务商管理员收到通知 → 确认接受
      ↓ 配置合约条款（角色/配额/到期日）和结算规则
      ↓ 服务商选择派遣哪些成员 → 绑定完成

路径 B：服务商主动申请
  服务商管理员 → 申请合作 → 搜索物业公司名称 → 提交申请
      ↓ 物业公司管理员收到通知 → 审批通过
      ↓ 配置合约和结算规则 → 绑定完成
```

#### 服务商发现与签约可见性原则（v0.5.4 澄清）

平台已审批通过（`audit_status='approved'`）的服务商，对**所有**物业租户可见，任一租户可在 `/admin/providers` 「邀请已审批服务商」列表里自由挑选并发起合作邀请，无需"先推荐再签约"前置。物业租户也可通过「推荐未入驻服务商」入口推荐平台尚未收录的服务商，由 OPS 审核入库 → 进入全平台可见的「已审批」池。

这条原则意味着：
- 平台扮演**服务商目录**角色（类似撮合市场），不做"绑定关系再可见"的强限制
- 同一审批通过的服务商可同时被多家物业租户邀请合作，形成 N×N 网状关系（`ProviderTenantContract` 表已支持）
- 私密性需求（某服务商只想给特定租户看见）当前不支持；如有此场景，未来可在 `ServiceProvider` 表加 `visibility` 字段（`public` / `invited_only`）扩展

---

### 17.4 内部员工账号创建

适用角色：内部催收员、主管/督导、法务专员、工单处理员（由所属物业公司或服务商管理员创建）。

```
管理员 → 用户管理 → 新建员工
        ↓
填写：姓名 / 手机号 / 角色 / 所属主管（可选）
        ↓
系统发送短信通知员工：
「您已被添加为[XX物业]的[催收员]，
 点击链接设置登录密码（24小时有效）：https://...」
        ↓
员工点链接设密码 → 账号激活，可立即登录使用
```

**批量导入：** 管理员可通过 Excel 模板批量创建内部员工（姓名+手机+角色），系统批量发送短信激活通知。

---

### 17.5 外部兼职账号邀请流程

适用角色：外部兼职催收员。**仅限邀请链接激活，不允许自主注册。**

```
管理员 → 用户管理 → 邀请外部兼职
        ↓
配置邀请参数：
  · 认领上限（该兼职最多持有多少条案件）
  · 合约到期日（到期账号自动停用）
  · 可访问时段（如：工作日 09:00-18:00）
        ↓
系统生成唯一邀请链接（7 天有效，单次使用）
  https://app.yzchuicui.com/invite/{token}
        ↓
管理员将链接发给兼职人员（微信/短信/邮件，系统外发送）
        ↓
兼职人员打开链接 → 手机号 + 验证码注册（实名绑定）
  · 若手机号已有账号：直接关联，获得新租户权限
  · 若是新用户：创建账号并关联
        ↓
账号激活，权限按配置生效
仅限 App 登录，号码脱敏，禁止导出
```

**邀请链接管理：**
- 管理员可查看已发出邀请的状态（待激活/已激活/已过期）
- 可手动作废未激活的邀请链接
- 同一手机号不能被同一租户邀请两次（去重校验）

---

### 17.6 账号生命周期管理

```
账号状态流转：

激活（ACTIVE）
    │
    ├─→ 管理员手动停用 ──────────────→ 已停用（SUSPENDED）
    │                                      │ 管理员恢复 ↓
    ├─→ 合约到期（expire_at 到期）──→ 已到期（EXPIRED）
    │                                      │ 续约后 ↓
    └─→ 管理员删除 ──────────────────→ 已删除（DELETED）
                                           （数据保留，账号不可登录）
```

**停用时的数据处理：**
- 停用账号：私海案件自动回公海，进行中的通话不中断
- 删除账号：逻辑删除，历史通话记录和结算记录保留（合规要求）
- 外部兼职到期：与停用同等处理，7 天缓冲期（防止突然中断工作）

---

### 17.7 行业参考对比

| 产品 | 企业账号 | 内部用户 | 外部合作方 |
|------|---------|---------|----------|
| Salesforce | 销售签约后后台开通 | 管理员邀请链接 | Partner Community 邀请制 |
| HubSpot | 自助注册（含免费试用） | 管理员邀请链接 | 独立合作伙伴门户 |
| 纷享销客 | 销售签约后后台创建 | 管理员直接创建 | 无 |
| **有证慧催** | **后台开通+试用申请表** | **直接创建+短信激活** | **邀请链接（限时限次）** |

### 17.8 Android App 分发策略

国内 Android 生态无统一应用商店，APK 分发采用以下方式：

| 阶段 | 分发方式 | 说明 |
|------|---------|------|
| MVP / 试用期 | 直链下载（官网/后台提供 APK 下载地址）| 管理员下载后通过企业微信/群发给员工 |
| v1.1 | 主流应用商店上架 | 华为应用市场、小米应用商店、OPPO 软件商店（覆盖 >80% 国内 Android 用户）|
| 企业版 | MDM 企业推送（可选）| 接入客户企业的移动设备管理平台，静默安装 + 强制版本更新 |

**版本更新机制**：
- App 启动时检查服务端版本号；发现新版本弹出提示（可选强制更新）
- 后端 `/api/app/version` 接口返回最新版本号 + 下载地址

---

| 类别 | 指标 |
|------|------|
| 实时辅助延迟 | 语音→话术卡片 P90 ≤ 3s，P99 ≤ 5s |
| 事后分析吞吐 | 5 分钟录音分析完成 ≤ 3min，支持 50 路并发 |
| 系统可用性 | SLA ≥ 99.5%（月） |
| 并发实时会话 | 初期 ≥ 20 路，架构支持扩展至 200 路 |
| 多租户数据隔离 | 所有接口强制 tenant_id 校验，禁止跨租户访问 |
| 录音加密 | 传输 HTTPS/WSS，静态 AES-256 |
| 手机号保护 | 数据库加密存储；外部兼职 API 返回脱敏值；转写文本正则脱敏 |
| 数据保留 | 录音默认 2 年，可配置 |
| 风控响应 | 关键词检测 < 50ms，LLM 确认 < 1s |
| 外部兼职数据防泄漏 | 禁止导出、禁止 PC 端登录、禁止查看完整号码 |

---

## 18. 话术库与 LLM 调优体系

> 核心目标：让每个物业公司/服务商能把自己积累的话术经验沉淀到 AI 里，同时平台持续优化基础模型，使 AI 提示准确率随使用量增长。

### 18.0 话术三层归属(v0.7.0 锁定)

`ScriptTemplate` 由 `tenant_id` + `provider_id` 两个字段决定归属:

| 层 | tenant_id | provider_id | 谁可读 | 谁可写 |
|---|---|---|---|---|
| 平台预置 | NULL | NULL | 所有人(物业 admin / 服务商 admin / agent) | 仅平台 OPS |
| 物业私有 | NOT NULL | NULL | 本租户内所有人(物业 admin / supervisor / agent) | 本租户 admin |
| 服务商私有 | NULL | NOT NULL | 本服务商内所有人 + 本服务商签约物业的 agent | 本服务商 admin |

**关键隔离规则**:
- **服务商不可读物业私有话术**(避免商业敏感)
- **物业不可读服务商私有话术**(同理)
- agent 在 PC 工作台看到的话术合并 = `平台预置 + 本租户私有 + (若属服务商)本服务商私有`

实现:`poc/backend/app/api/{admin_scripts,provider_scripts}.py` GET 端点用 `or_(...)` 表达三层合并;CRUD 写端点严格按所属层校验。

### 18.1 话术库管理（租户级）

#### 话术条目结构

每条话术由四个字段构成：

| 字段 | 说明 |
|------|------|
| 触发意图 | 业主说话中检测到的意图，如"质疑物业费合理性" |
| 异议关键词 | 触发该条话术的匹配词组（支持多个，OR 关系） |
| 推荐话术 | 催收员可直接使用的回应语句 |
| 补充说明 | 给 AI 的额外上下文（不显示给催收员） |

**示例：**

| 触发意图 | 异议关键词 | 推荐话术 | 补充说明 |
|----------|-----------|---------|---------|
| 质疑费用合理性 | 凭什么收、凭什么涨 | "您好，本次费用按政府备案价执行，我们可以发给您政府备案文件和收费明细单……" | 若业主提到水费电费一同计算，说明分项计费规则 |
| 推迟付款 | 下个月、等发工资、过几天 | "没问题，您方便的话我帮您记一个大概日期，到时候我们会发提醒通知……" | 重点是获取承诺日期，不要强迫立即付款 |
| 房屋质量问题 | 漏水、墙裂、电梯坏 | "您反映的问题我已经记录下来，工单已经提交给维修部，同时关于物业费……" | 先处理情绪，再引导物业费话题 |
| 拒绝沟通 | 挂电话、不想谈、烦死了 | "好的，打扰您了，如果您有时间欢迎随时回拨我们……" | 礼貌收尾，避免激化 |

#### 话术库 UI（租户管理员 / 督导）

- **列表页**：触发意图 + 话术摘要 + 启用状态 + 最近更新 + 综合评分（A/B/C/D）
- **编辑页**：表单填写 + 实时预览（模拟 AI 推送卡片样式）
- **批量导入**：Excel 模板上传，字段自动映射
- **版本历史**：每次保存生成快照，可一键回滚
- **启用/禁用**：不删除数据，支持随时切换

#### 话术库工作方式（运行时 Prompt 组装）

```
[System Prompt]
= base_prompt（平台基础指令，含角色定义 + 输出格式）
+ tenant_context（租户行业/楼盘背景）
+ active_scripts（当前租户启用的话术条目，格式化为 few-shot 示例）
+ risk_keywords（租户自定义 + 平台全局风控词）

[User Message]
= 实时 ASR 文本流（最近 N 句，滚动窗口）
+ conversation_summary（通话摘要，超过 20 句后压缩）
```

few-shot 示例插入格式（最多取 Top 5 相关条目）：
```
示例-1:
业主说："凭什么收这么多？"
推荐回应："您好，本次费用按政府备案价执行……"
```

### 18.2 多源反馈采集

AI 提示质量的提升依赖三个信号来源：

#### 信号 1：催收员实时反馈（通话中）

催收员在 App 实时工作台上，每条 AI 话术卡片底部有：
- 👍 采用（点击后该建议高亮标记为"已采用"）
- 👎 忽略（点击后标记为"已忽略"，可选填原因：不准确/不合适/已说过）

#### 信号 2：督导事后标注

督导在复核工作台，查看通话录音 + ASR + AI 推送历史，可对每条话术打标：
- ✅ 好话术（应继续推送）
- ❌ 差话术（应停用或调整）
- ✏️ 改进建议（自由文本）

#### 信号 3：业务结果推断（自动）

通话结束后，系统自动关联业务结果：
- 业主承诺付款 / 实际付款 → 通话中被采用的话术获得正向权重
- 业主情绪升级 / 投诉 → 通话中被推送的话术获得负向权重
- 无明确结果 → 中性，不参与计算

#### 反馈数据模型

```sql
CREATE TABLE suggestion_feedback (
    id                BIGSERIAL PRIMARY KEY,
    tenant_id         INT NOT NULL,
    call_record_id    BIGINT NOT NULL,
    script_template_id INT,              -- 关联话术条目（NULL = 平台基础推送）
    suggestion_text   TEXT NOT NULL,     -- 实际推送的话术内容（快照）
    was_presented     BOOLEAN NOT NULL,  -- 是否展示给催收员
    agent_action      VARCHAR(20),       -- adopted / ignored / null
    ignore_reason     VARCHAR(50),       -- inaccurate / inappropriate / already_said
    supervisor_label  VARCHAR(20),       -- good / bad / improve
    supervisor_note   TEXT,
    call_result       VARCHAR(30),       -- paid / promised / refused / escalated / neutral
    inferred_signal   SMALLINT,         -- +1 / -1 / 0（系统自动计算）
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
```

### 18.3 话术效果分析看板（督导/管理员）

每周自动生成话术效果报告，核心指标：

| 指标 | 说明 |
|------|------|
| 推送次数 | 该话术在选定时间内被 AI 推送的总次数 |
| 采用率 | 催收员点击"采用"的比例 |
| 转化率 | 被采用后通话最终转化（承诺/付款）的比例 |
| 督导好评率 | 督导标注"好话术"的比例 |
| 综合评分 | 加权计算：采用率×0.3 + 转化率×0.5 + 督导好评率×0.2，分 A/B/C/D 四档 |

评分规则：
- **A 级**（≥ 0.7）：优质话术，系统优先推送，Prompt 中 few-shot 权重提升
- **B 级**（0.5-0.7）：正常话术，维持现状
- **C 级**（0.3-0.5）：低效话术，系统标黄警告，建议管理员优化
- **D 级**（< 0.3）：无效话术，系统自动禁用（管理员收到通知，可手动重新启用）

看板 UI 包含：
- 话术效果排行榜（可按时间段筛选）
- 按触发意图分组的效果汇总
- 单条话术的完整反馈明细（可下钻查看具体通话）
- 导出 Excel

### 18.4 平台级 Prompt 版本管理与 A/B 测试

#### Prompt 版本管理

平台超管可维护多个 base_prompt 版本：

```
base_prompt_v1.2（当前稳定版）
base_prompt_v1.3（灰度测试中）
base_prompt_v1.4（草稿）
```

每个版本记录：创建人、创建时间、备注说明、关联测试结果。

#### A/B 测试配置

| 参数 | 说明 |
|------|------|
| 测试名称 | 如"v1.2 vs v1.3 长话术对比" |
| 流量分配 | 按租户分组（A 组用 v1.2，B 组用 v1.3）或按比例随机 |
| 观测指标 | 采用率、转化率、通话时长、督导好评率 |
| 运行时长 | 通常 1-2 周，足够样本量后停止 |
| 结果判断 | 置信度 ≥ 95% 且指标提升 ≥ 5% 才判为有效改进 |

A/B 测试结束后：
- 胜出版本晋升为稳定版，全量推送
- 失败版本归档，保留数据供参考
- 支持一键回滚到上一个稳定版本

#### 跨租户脱敏学习

各租户的 suggestion_feedback 数据脱敏后汇入平台级分析：
- 去除公司名称、具体楼盘、业主信息
- 保留意图分类 + 话术模板 + 反馈信号
- 用于识别跨租户通用的高效话术模式
- 平台定期（每月）提炼为 base_prompt 的优化建议，由超管审核后发布

### 18.5 后台配置项清单

#### 租户管理员可配置

| 配置项 | 说明 |
|--------|------|
| 话术库管理 | 增删改查，支持导入/导出 |
| 话术启用/禁用 | 控制哪些条目进入实时 Prompt |
| 单次推送话术数量上限 | 默认 3 条，可调 1-5 |
| 自定义风控关键词 | 补充平台全局词库之外的敏感词 |
| AI 推送灵敏度 | 高/中/低，控制触发阈值 |
| 承诺付款短信模板 | 业主收到的确认短信内容 |

#### 平台超管可配置

| 配置项 | 说明 |
|--------|------|
| base_prompt 版本管理 | 编辑/发布/回滚 |
| A/B 测试管理 | 创建/运行/结束/归档 |
| 全局风控关键词 | 适用所有租户 |
| 默认 LLM 参数 | temperature、max_tokens、top_p |
| 跨租户学习开关 | 是否允许租户数据参与平台级优化（默认开启，需租户同意） |
| 脱敏学习发布审核 | 平台优化建议的发布审批流程 |

---

## 19. MVP 范围（第一版）

### 包含

**Android App**
- 催收任务列表（私海）+ 公海认领
- PC 触发拨号（DIAL_REQUEST）+ App 主控拨号
- 实时三段式通话界面（AI 话术卡片）
- 风控三级干预（L3 默认关闭，管理员可在系统配置中启用）
- 支付信息二维码展示（MVP 静态展示，无在线支付）
- 通话后快速标记
- 录音模式：优先实时推流，网络差时自动降级为本地录音+事后上传
- App 后台通知接收（Android 厂商推送，确保锁屏/后台时 DIAL_REQUEST 能到达）

**PC 端**
- 催收 CRM（列表视图 + 看板视图 + 案件详情页+活动时间线）
- 通话实时工作台（三栏）
- 快捷操作面板（发二维码 / 建工单 / 转接）
- 公海/私海管理（手动分配为主）
- 业主名单 Excel 导入
- **缴费链接 + 收款配置（v2.2 已交付）**：项目级 4 收款字段 + payment_mode；`payment_link` token 持久化（7 天）；发送弹窗展示「应缴 − 已减免 = 应支付」明细 + 待审批减免非阻断提醒；公开 H5 账单页 `/pay/:token` 实时计算应付额；详见 §14（v1.1 加在线支付通道 + 公证提存）
- 录音批量上传 + 事后分析
- 管理员分析看板（今日概览 + 排名）
- 督导复核工作台（基础版）
- 工单管理（基础版）
- 法务案件管理（基础版）
- 用户管理（6 个角色，含外部兼职邀请链接、批量 Excel 导入）

**账号开通（平台运营后台）**
- 后台创建租户（公司名称/管理员手机/套餐/有效期）
- 短信通知管理员激活
- 14 天试用账号开通（限 5 用户 + 50 案件）
- 平台运营查看自己负责（已分配）的租户列表

**后端**
- 多租户基础架构（单租户先用，接口已隔离）
- WebSocket 信令 + 音频推流
- DashScope ASR + Qwen-Plus LLM
- Celery 异步任务队列
- 手机号 AES-256 加密存储 + 脱敏输出
- 关键数据 SHA-256 哈希字段预埋（data_hash 列，为 v1.1 区块链存证准备）
- 支付信息 H5 页面 + 二维码生成接口（MVP 静态展示）
- Android 厂商推送集成（小米/华为/OPPO Push，覆盖主流机型后台通知）
- 邀请链接生成与校验（token + 过期时间 + 单次使用）
- 账号生命周期管理（停用/到期/删除 + 案件自动回公海）
- 通话分钟池化配额：per-tenant 月度配额设置、用量实时累计（`tenant_minute_usage`）、超额拦截中间件、80%/95%/100% 三级预警通知

**结算管理（基础版）**
- 结算规则配置（合约级别：计费方式/单价/周期）
- 月末自动生成结算单草稿
- 结算单明细查看（按成员/按案件）
- 物业公司管理员确认结算单
- 付款凭证上传 + 标记已付款
- 服务商管理员查看应收账款
- 结算异议提交
- Excel/PDF 账单下载

**话术库与 LLM 调优（基础版）**
- 话术库管理 UI（增删改查 + Excel 导入 + 启用/禁用 + 版本历史回滚）
- 运行时动态 Prompt 注入（话术条目自动格式化为 few-shot 示例）
- 催收员通话中话术卡片采用/忽略反馈（信号 1）
- 督导事后标注好/差话术（信号 2）
- 业务结果自动推断信号（信号 3，付款/承诺 = 正向，投诉 = 负向）
- 话术效果周报看板（采用率 + 转化率 + 综合评分 A/B/C/D）
- D 级话术自动禁用并通知管理员
- suggestion_feedback 数据表及写入逻辑
- 租户管理员可配置：推送数量上限 / 灵敏度 / 自定义风控词

### 推迟到 v1.1

- CRM 自动流转规则引擎（定时任务）
- 完整多租户隔离（多 schema）
- 服务商在线申请入驻 + 审核流程（MVP 由平台后台手动创建）
- 服务商与租户双向绑定流程（MVP 由管理员手动配置）
- 多租户合并视图（工作空间选择页）
- 深度数据报表（趋势图/员工对比/结算趋势）
- 企微/钉钉通知集成
- Android 离线缓存
- 在线支付接入（微信/支付宝 sub_mch，支付页含直接付款 + 公证提存两种模式）
- 结算异议自动化处理流程
- 平台超管结算总览
- 平台级 base_prompt A/B 测试框架
- 跨租户脱敏学习与 Prompt 优化发布流程
- 话术库按触发意图的多维分析（下钻到具体通话明细）

### MVP 验收标准

1. 通话中 AI 话术卡片延迟 ≤ 3s（P90）
2. PC 点击拨打后 App 弹出通知延迟 ≤ 2s
3. 事后分析标签准确率经督导核验 ≥ 75%
4. 外部兼职全程看不到完整手机号，无法导出任何数据
5. 邀请链接 7 天有效、单次使用，激活后权限立即生效
6. 月末自动生成结算单，管理员可在系统内完成确认和付款记录全流程
7. 话术库导入后，实时 AI 推送能准确引用对应话术（人工验证 ≥ 3 个场景）

---

## 20. 商业模式与变现路径

> 有证慧催的商业模式分三个阶段演进：工具订阅（0-1）→ 行业中台（1-3）→ 数据+法律服务平台（3+）。
> 各收入线独立开关，可根据市场反馈逐步打开。

### 20.1 核心收入：SaaS 订阅

**定价分层建议（参考）**

| 套餐 | 月费 | 核心限制 | 目标客户 |
|------|------|---------|---------|
| 试用版 | 免费 14 天 | 5 用户 / 50 案件 / 无结算模块 | 获客钩子 |
| 基础版 | ¥1,980/月 | 15 用户 / 500 案件 / 基础看板 | 小型物业（500-1000 户）|
| 专业版 | ¥4,980/月 | 50 用户 / 无限案件 / 服务商模块 / 合规存证报告 | 中型物业（1000-5000 户）|
| 企业版 | 面议 | 私有部署 / 多楼盘隔离 / 专属 SLA | 大型物业集团 |

计费维度可灵活叠加：
- 按**座席数**收费（适合团队稳定的物业公司）
- 按**案件量**收费（适合季节性业务或按结果付费偏好）
- 按**AI 通话分钟数**计费（适合大账期企业，控成本）

#### 20.1.1 通话分钟池化配额机制

MVP 阶段采用**平台统一池化**模型：平台维护全局通话分钟池，由平台运营员按合同向每个租户（物业公司或服务商）分配月度配额，租户内部共享该配额，不再向单个用户拆分。

**配额层级**

```
平台总池（无硬上限，按实际用量计费）
    │
    ├── 租户 A（物业公司）：月度配额 N 分钟  ← 平台运营员设置
    │       └── 内部催收员 1、2、3 … 共享该配额
    │
    ├── 租户 B（服务商）：月度配额 M 分钟
    │       └── 团队成员共享该配额
    │
    └── … 其余租户
```

**配额设置流程**

1. 平台运营员在「租户详情」（页面 2.3）为每个租户设置本月通话分钟配额
2. 租户管理员在自身管理看板可查看本月已用 / 剩余分钟，但**不能自行调整配额**
3. 运营员可随时临时提额（写入当月覆盖值），提额操作记入跟进时间线

**各角色可见粒度**

| 角色 | 可见内容 |
|------|---------|
| 平台超管 | 全平台总用量 + 成本汇总 + 各租户用量明细 |
| 平台运营员 | 所负责租户的本月用量 / 配额 / 剩余 + 配额设置入口 |
| 物业公司管理员 | 本公司本月已用分钟 / 配额 / 剩余 |
| 服务商管理员 | 本服务商本月已用分钟 / 配额 / 剩余 |
| 主管/督导 | 团队本月通话分钟趋势（无配额字段，仅用量） |
| 内部催收员（PC + App）| 本人本月累计通话分钟数 |
| 外部兼职催收员（App）| 本人本月累计通话分钟数 |
| 法务专员 / 工单处理员 / 项目负责人 | 不展示通话分钟字段 |

**超配额行为（v1.3 引入软配额）**

| 阈值 | 触发动作 |
|------|---------|
| 用量达配额 **80%** | 系统推送预警通知给租户管理员 + 平台运营员 |
| 用量达配额 **95%** | 管理员看板显示醒目警告横幅；运营员收二次提醒 |
| **dial-start 检查：剩余 < 3 分钟** | **软配额拦截**：拒绝新发起通话（403 ERR_QUOTA_EXHAUSTED），但已在通话中的不挂断（避免半路砍断）|
| 通话中超额（剩余分钟用尽） | **不挂断**，仅推 risk 事件 `quota.exhausted` 到 PC 风控告警；下一通拒绝；超的部分计入下月透支额度 |
| 运营员手动临时提额 | 立即生效，当月超出部分按合同宽限条款或超额单价计费 |

> 拦截逻辑在后端 dial-start API 层强制执行，不依赖前端，确保绕不过去。
> upload 端做兜底校验防客户端篡改本地状态绕过。

**计量规则**

- 计量粒度：**秒**，账单按分钟向上取整（不足 1 分钟按 1 分钟计）
- 仅计量「接通时长」：ASR 推流开始 → 通话挂断；未接通、占线、空号**不计入**
- 数据来源：`call_record.billable_duration`（秒），汇总至 `tenant_minute_usage` 月度统计表

**实时 vs 事后分别计费（v1.3，Sprint 14.1）**

实时通话（live：通话进行中走 WebSocket + ASR 实时转写 + AI 提示）与事后上传（post：通话结束后批量上传录音再转写）资源成本差约 3×（实时占 ASR live 通道 + LLM token，事后仅 ASR 批处理）。系统支持分别统计与计费：

- 模式决议：dial-start 时按 TenantSettings.recording_mode 决议并**冻结**到 `CallRecord.recording_mode`，事后改 settings 不影响进行中的通话
- `auto` 模式决策：当前 realtime 余量 ≥10 分钟 → live；否则降级 post
- 看板分别展示：admin/dashboard/stats 与 super/cost/dashboard 同时返回 realtime/post 拆分字段，PC 端分两条柱状图

**数据模型新增字段**

| 表 | 新增字段 | 说明 |
|----|---------|------|
| `tenant` | `monthly_minute_quota` INT | 当前月度配额（分钟），NULL 表示无限制（企业版面议合同）|
| `tenant` | `minute_quota_updated_at` | 最后一次配额修改时间 |
| `call_record` | `billable_duration` INT | 可计费秒数（接通后到挂断，不含振铃）|
| `call_record` | `recording_mode VARCHAR(16)` (v1.3) | live / post，dial-start 时冻结，CHECK 约束 |
| `call_record` | `last_heartbeat_at TIMESTAMPTZ` (v1.3) | agent App 30s 一次心跳；超时清理 |
| `call_record` | partial unique index `uq_active_call_per_caller` (v1.3) | 同一坐席不能并发拨号 |
| `tenant_minute_usage` | `used_minutes` INT | 月度总用量（兼容字段 = realtime + post）|
| `tenant_minute_usage` | `realtime_minutes` INT (v1.3) | 实时模式用量子项 |
| `tenant_minute_usage` | `post_minutes` INT (v1.3) | 事后模式用量子项 |
| `plan_config` | `monthly_minutes` INT | 套餐总配额 |
| `plan_config` | `monthly_realtime_minutes` INT (v1.3) | 套餐细分配额，NULL 表示不分别拦截 |
| `plan_config` | `monthly_post_minutes` INT (v1.3) | 套餐细分配额 |

**单价 + 金额计费（v0.5.9 落地）**

通话分钟单价由 `BillingPricing` 表单例维护，由平台 OPS 调整。MVP 初始值：

| 字段 | 初始单价 | 含义 |
|------|---------|------|
| `minute_price_live` | ¥0.5 / 分钟 | 实时模式(走 ASR live 通道) |
| `minute_price_post` | ¥0.3 / 分钟 | 事后模式(批处理 ASR) |

`tenant_minute_usage` 表的 `realtime_minutes` / `post_minutes` 已有分模式拆分,直接按上述单价计算月度金额,不需新增 `cost_amount` 字段。

**前端入口（v0.5.9）**：
- 物业 admin：`/admin/billing/minute-usage` — 月份选 + 4 KPI 卡(实时/事后/总额/剩余配额) + 6 月堆叠条趋势
- 服务商 admin：`/provider/billing/minute-usage` — 跨租户明细(基于 `ProviderTenantContract` 找本服务商接的所有 active 合作租户,按金额降序)

后端：
- `GET /api/v1/admin/billing/minute-summary?year_month=YYYY-MM`
- `GET /api/v1/admin/billing/minute-trend?months=N`
- `GET /api/v1/provider/billing/minute-summary?year_month=YYYY-MM`

---

### 20.2 服务商撮合与抽佣

**当前阶段（MVP）**：服务商由平台后台手动入驻，物业公司管理员手动配置合作。

**v1.1 撮合市场（Marketplace）**：

```
服务商主页
├── 基本信息（机构名称 / 资质证书 / 擅长类型）
├── 服务能力（催收 / 法务 / 双语 / 专项楼盘类型）
├── 业绩指标（平台认证：回款率 / 平均周期 / 服务案件数）
└── 用户评价（物业公司匿名评分）

物业公司发布需求
├── 案件类型 / 欠费规模 / 期望回款率
└── 系统自动推荐匹配服务商 Top 3

签约后平台收成交金额 3-5% 撮合费
```

网络效应：服务商越多 → 物业公司选择越多 → 平台越有价值 → 吸引更多服务商入驻。

---

### 20.3 政企合规存证服务（重点）

#### 背景与合规压力

2021 年《个人信息保护法》、2022 年《互联网信息服务算法推荐管理规定》明确要求：
- 催收行为必须全程可追溯，不得骚扰
- 录音需安全存储、可随时调取
- 物业公司若发生业主投诉，必须提供"合规催收行为证明"
- 上市物业集团需在年报/ESG 报告中说明催收合规情况

**现有系统天然具备合规存证能力**，通过区块链链上存证实现不可篡改的司法级证据。

#### 合规存证的技术基础：区块链上链

系统采用**区块链存证**替代传统 CA 签章，每条关键数据写入时自动计算哈希并上链，链上交易哈希即是防篡改证明：

| 数据项 | 存储位置 | 上链时机 | 存证价值 |
|--------|---------|---------|---------|
| 通话录音原文件哈希 | MinIO / OSS（AES-256 加密）| 上传完成后 | 证明录音内容不可篡改 |
| ASR 全文转写哈希 | transcript 表 | 写入时 | 可检索的文字证据 |
| 通话时间戳 + 发起人 | call_log 表 | 通话结束时 | 证明何时、谁发起 |
| AI 推送话术快照哈希 | suggestion_feedback 表 | 推送时 | 证明催收内容符合规范 |
| 风控干预记录哈希 | risk_event 表 | 触发时 | 证明平台主动阻止了违规行为 |
| 公证提存证书哈希 | payment_record 表 | 生成时 | 资金托管合规性证明 |

**区块链平台选型**（三选一，v1.1 确定）：
- **蚂蚁链司法存证**：已接入最高人民法院电子诉讼平台，存证结果直接可在法院核验
- **腾讯至信链**：接入广州、深圳互联网法院，适合南方客户
- **人民法院电子诉讼平台（PPIP）**：直接对接法院系统，司法效力最强

```
数据产生 → SHA-256 本地哈希 → 调用区块链 SDK 上链
    ↓
链上返回：tx_hash（交易哈希）+ block_height（区块高度）+ timestamp
    ↓
写入 blockchain_proof 表（data_id, data_type, data_hash, tx_hash, chain, created_at）
    ↓
法务需要时：出具「区块链存证证明」= 原始数据 + tx_hash + 链上核验 URL
```

#### 合规存证产品形态

**① 合规行为月报（自动生成，随专业版/企业版附赠）**

```
XX 物业 2026年3月 合规催收行为月报
─────────────────────────────────
本月催收通话：348 次
平均每日外呼次数：11.2 次/人（行业建议 ≤ 20 次）
单一业主最高接触次数：4 次（未超过行业规范 6 次/月上限）
AI 风控干预：L1 提醒 23 次，L2 警告 2 次，L3 自动终止 0 次
录音存储状态：348/348 完整存储，区块链存证 348/348 通过
个人信息处理：外部人员全程脱敏，无完整号码泄露
─────────────────────────────────
月报区块链存证哈希：0xabcd...ef01
可通过 https://chain.verify.xxx 核验本报告真实性
```

**② 单案存证包（按需付费）**

当某个欠费案件进入法务追诉流程，催收员/律师可导出该案件的完整存证包：

```
案件存证包（案件号：CASE-20260315-0042）
├── call_timeline.pdf      通话时间线（图示 + 文字）
├── recordings/            所有相关录音 zip（含 SHA-256 + 链上 tx_hash）
├── transcripts.pdf        ASR 转写全文（带时间戳 + 链上核验码）
├── ai_activity.pdf        AI 推送话术记录（证明内容规范）
├── risk_events.pdf        风控事件日志（含无违规证明）
├── payment_escrow.pdf     公证提存证书（如适用）
└── blockchain_cert.pdf    区块链存证汇总证明（所有 tx_hash 列表 + 核验入口）
```

**定价**：¥99/案件（单买）；专业版每月赠 10 次，企业版无限次。

**③ 年度合规审计报告（企业版 / 上市公司专项）**

- 全年催收行为统计，含趋势图、峰谷分析、员工行为热图
- 区块链存证数据核验摘要（链上可独立验真）
- 合规改进建议（对标行业规范差异点）
- 可用于年报附件 / 监管检查 / 物业公司招投标资质证明

**定价**：¥9,800/年（需企业版套餐）

#### 合规存证的战略价值

1. **降低签约阻力**：物业公司决策层担心"AI 催收是否合规"，链上存证直接消除顾虑
2. **司法直通**：蚂蚁链/至信链存证可在法院系统直接核验，无需额外公证，法务成本大幅降低
3. **形成转换壁垒**：链上存证数据与案件强绑定，换平台无法迁移历史存证链
4. **政府关系窗口**：区块链合规报告可作为向主管部门展示行业自律的材料

#### 合规存证 PRD 需求点

| 模块 | 说明 | 优先级 |
|------|------|--------|
| SHA-256 数据哈希计算 | 关键数据写入时自动计算哈希，存入 data_hash 字段 | MVP |
| blockchain_proof 数据表 | 存储 tx_hash、block_height、chain 等链上回执 | v1.1 |
| 区块链 SDK 集成 | 对接蚂蚁链/至信链，异步上链（不阻塞主流程）| v1.1 |
| 合规月报自动生成 | 月末 Celery 任务触发，模板渲染 + PDF 导出，含区块链核验码 | v1.1 |
| 单案存证包导出 | 录音 + 转写 + AI 记录 + 链上证明打包下载 | v1.1 |
| 区块链核验入口页 | 公开可访问的核验页面，输入 tx_hash 显示原始数据摘要 | v1.1 |
| 年度审计报告 | 定制化，企业版 + 运营人工参与 | v2.0 |

#### 单次存证计费（v0.5.9 落地）

存证服务商优先选用「易保全」(ebaoquan.org),由 `BlockchainConfig` 单例 active 配置控制(超管页面 `/super/blockchain-config` 维护)。
单次存证费用由 `BillingPricing` 表维护:

| 字段 | 初始单价 | 适用 data_type |
|------|---------|---------------|
| `blockchain_price_per_attestation` | ¥5 / 次 | call_recording / transcript / analysis |
| `blockchain_price_per_case_bundle` | ¥99 / 次 | evidence_bundle(案件级整包) |

存证写入 `BlockchainAttestation` 时,从 active `BillingPricing` 读单价并冻结写入 `cost_amount` 字段(NULL 表示未配置单价的兼容场景)。
失败的上链调用(`status=failed`)不收费 — 仅 confirmed 计入。

**前端入口（v0.5.9）**：
- 物业 admin：`/admin/billing/blockchain` — 月份选 + KPI(次数/总额/provider 状态) + 类型分布 + 列表(可点 tx_hash 跳验证页)
- 法务专员：法务案件详情页 → 「下载存证包」按钮(已实现)

后端:
- `GET /api/v1/admin/billing/blockchain-summary?year_month=YYYY-MM`
- `GET /api/v1/admin/billing/blockchain-attestations?page=1&page_size=30`

#### 20.3.5 法律效力分级 + 触发策略(v0.8.0 锁定)

v0.8.0 将存证从「一刀切的成本项」重塑为「分级的诉讼证据」。核心问题不是"该不该上链",而是"什么时候、对什么数据上链"。

**法律效力三级模型**

| 等级 | 数据存在形式 | 证据强度 | 法律依据 | 法庭采信度 |
|------|----------|--------|--------|----------|
| 🔴 **本地哈希(弱证据)** | `data_sha256` 字段(原始数据进库瞬间计算)| 仅平台单方面计算 | 无第三方背书 | 对方律师可主张「平台自证」、要求出示原始服务器日志 |
| 🟡 **第三方区块链存证(强证据)** | `BlockchainAttestation` row + tx_hash + 易保全保全备案号 | 第三方司法链 + 时间戳 + 哈希不可变 | **最高法 2018 第 11 号文**(《最高人民法院关于互联网法院审理案件若干问题的规定》第 11 条):「电子数据通过电子签名、可信时间戳、哈希值校验、区块链等证据收集、固定和防篡改的技术手段或者通过电子取证存证平台认证,能够证明其真实性的,互联网法院应当确认」 | **互联网法院直接核验**,无需对方反复质疑 |
| 🟢 **公证处提存(最强证据)** | 不在本系统范围 | 公证书 | 《公证法》| 不实现 — 仅大额案件法务自行送公证 |

> v0.8.0 平台只做 🔴 + 🟡 两级,🟢 由法务在律师函/诉状里附公证书路径(系统不强耦合)。

**触发策略 — 何时升级 🔴 → 🟡**

| 数据类型 | 默认状态 | 升级触发点 | 成本 | 经济模型 |
|---------|--------|----------|-----|--------|
| 通话录音(call_recording)| 🔴 本地哈希 | 法务案件「打包上链」单一入口 | ¥5/单 × 数量 或 ¥99/案件包 | 99% 案件不进诉讼 → 不上链 = 零成本;1% 进诉讼 → 该案件单次 ¥99 全量上链 |
| 转写文本(transcript)| 🔴 本地哈希 | 同上(随案件包) | 同上 | 同上 |
| AI 分析(analysis)| 🔴 本地哈希 | 同上(随案件包) | 同上 | 同上 |
| L2 风险事件(`RiskEvent.level='L2'`)| 🟡 **pending 标记** | 督导处置时(`mark_pending_attestation`)自动写 `BlockchainAttestation` 但 tx_hash=NULL / cost=NULL — 即「待上链」预占位 | ¥0(标记成本零) | 法务后续打包时一并上链(已预占位,免重复扫描)|

**为什么 L2 风险事件特殊?** L2 = 督导主动介入处置的合规风险(冲突升级、不当承诺、催收话术违规),这类事件本身就是「诉讼准备阶段最可能被对方反向引用的证据」 — 不能丢、不能改。v0.8.0 选择「**先标记、不立即调链**」策略(决策 1c):

- 优势:**零成本**(无 API 调用)+ **同等法律效力**(法务打包时一并上链,时间戳追溯仍有效 — 司法链关心的是 hash 上链时刻而非数据生成时刻)
- 风险:法务忘记打包 → pending 行永远不升级 → 与「仅本地哈希」无异
- 缓解:法务案件详情页 `EvidenceStatusPanel` 显示「待上链 N 件」黄色徽章,打包上链时 `attest_case_only()` 自动捞 pending 行

**受众边界(只给法务 + 物业管理员看)**

| 角色 | 看证据状态 | 看法律效力提示 | 看费用 / 触发上链 |
|------|---------|------------|--------------|
| 法务(`role='legal'`)| ✅ 完整 4 类细分 | ✅ 弱/混合/强三档 | ✅ 主入口「打包上链 ¥99」 |
| 物业管理员(`role='admin'`)| ✅ 案件徽章 + 月度风险敞口 | ✅ 三态外观(strong/pending/weak)| ⚠️ 不直接触发 — 通过「转法务时一并上链」勾选 |
| 项目经理 / 督导 | ✅ 案件徽章只读 | ✅ 同 admin | ❌ 不可触发 |
| 催收员 / 业主 | ❌ 不暴露 | ❌ 不暴露 | ❌ 不暴露 — 避免恐慌 / 心理压力 |

**前端入口(v0.8.0 新增)**

- 法务专员:`/legal/cases/{lc_id}` 顶部「证据状态」面板 — 4 行 4 类对比表 + 弱/强提示 + 3 按钮(打包上链 ¥99 / 下载证据包 / 生成证据清单 HTML)
- 物业管理员:
  - `/admin/cases/{case_id}` 右栏 sticky「证据状态」小卡片 — 三态色边 + 总数 + CTA
  - `/admin/billing/blockchain` 升级为「存证管理」双 tab — 计费视图(原)+ 风险敞口(新:本月新增 / 已强化 / 仅本地 + 大额未上链 Top 10)
- 平台公开核验:`GET /api/v1/public/verify/{tx_hash}` 返回元数据 + 易保全官方核验 URL(借公信力)

**后端入口(v0.8.0 新增)**

- `POST /legal/cases/{lc_id}/attest` — 法务打包上链(`attest_case_only`,幂等)
- `GET /legal/cases/{lc_id}/evidence-status` — 4 类细分聚合
- `GET /legal/cases/{lc_id}/evidence-receipt?token=xxx` — HTML 证据清单(浏览器打印为 PDF)
- `GET /admin/cases/{case_id}/evidence-status` — admin 徽章用,返回摘要
- `GET /admin/blockchain/risk-overview?year_month=YYYY-MM` — 风险敞口 tab 数据源
- `app.services.blockchain.mark_pending_attestation()` — L2 标记(零成本)
- `app.api.supervisor_extras.annotate_risk_event` PATCH — L2 处置时自动 hook

> 完整决策日志见 §22.12。

---

### 20.4 法务转化通道

工单/法务模块已在 PRD 中定义为内嵌跟进工具，本节将其升级为**独立收入线**。

**流程**

```
CRM 案件 → 多次催收无果 → 一键"转法务追诉"
    ↓
系统自动生成：
  - 催收行为时间线摘要
  - 系统推荐处理方式（律师函 / 小额诉讼 / 申请仲裁）
  - 预估法律成本与回款概率（基于同类案件历史）
    ↓
物业公司选择服务包 → 平台分配合作律所 → 律所在法务工作台接单
    ↓
平台收取介绍费（法律服务费的 20-30%）
```

**转法务入口(v0.6.0)— 双路径**

转法务有两条互斥路径,详见 [§4.4 法务转化双路径](#44-法务转化双路径v060):

- 路径 A:**催收员申请 → 督导审批**(主流程,有 LegalConversionRequest 单据)
- 路径 B:**督导直接移交**(越权,无单据,需填原因 audit log)

后端 `POST /supervisor/cases/{id}/transfer-legal` 校验:若本案件已有 status ∈ (pending, pending_admin) 的 LegalConversionRequest,返回 409 防双轨。督导侧案件详情页按钮按 `pending_legal_conversion_request_id` 是否为 NULL 条件渲染「移交法务」或「审批转法务」。

法务转化订单详情页(v0.6.0)新增「区块链存证」section,后端 `GET /admin/legal-conversion-orders/{id}/attestations` 走 `LegalConversionOrder → CollectionCase → LegalCase → BlockchainAttestation` 链,展示该案件下所有 confirmed 上链记录(时间 / 类型 / 金额 / tx_hash 链接到公开核验页)。

**服务包设计**

| 服务包 | 内容 | 参考定价 |
|--------|------|---------|
| 律师函发送 | 加盖律所公章的催款律师函 + 邮寄送达 | ¥199/件 |
| 诉前调解 | 律师代发调解通知 + 电话协商 | ¥399/件 |
| 小额诉讼协助 | 诉状准备 + 材料提交指导（物业公司自行出庭）| ¥599/件 |
| 完整代理 | 律师全程代理起诉至执行 | 面议（成功分成） |

**战略意义**：物业公司目前的痛点是"欠费额小，请律师不划算，所以业主不怕"。平台把法律威慑门槛从 5000 元降到 199 元，直接改变博弈结构。

---

#### 20.4.1 v1.5 实施落地

**数据模型（共 6 张表）**

| 表 | 用途 |
|---|---|
| `legal_service_package` | 服务包目录（4 个平台默认 + 租户级覆盖）；含 `package_type` ∈ {lawyer_letter, mediation, small_claims, full_agency}、`price`、`platform_fee_rate` |
| `legal_conversion_order` | 案件转化订单。状态机 `pending → dispatched → in_service → completed`（或 `cancelled`）；订单创建时冻结 `timeline_summary`/`recommendation`/`cost_estimate` 三块 JSONB |
| `law_firm` | 律所池（平台 ops 维护）；含 `accepting_orders`、`rating_avg`、`completed_orders` 自增计数 |
| `law_firm_lawyer` | 律师从属于律所；订单 dispatch 时可选指定律师，名字快照入订单审计字段 |
| `legal_platform_invoice` | 律所→平台介绍费按月账单。`unique(law_firm_id, period_start, period_end)` 防重复生成；`DRAFT → CONFIRMED → PAID` 三态 |
| `legal_document_template` + `legal_document_render` | 文书模板目录 + 多版本渲染产物。模板 mustache `{{var}}` 占位，按 `(tenant_id, package_type)` 查找时优先租户级 override |

**平台分成默认率**（订单创建时按服务包 `platform_fee_rate` 冻结到订单）

| 服务包 | 默认费率 | 单笔分成（基础价 × 费率） |
|---|---|---|
| 律师函发送 | 30% | ¥59.70 |
| 诉前调解 | 25% | ¥99.75 |
| 小额诉讼协助 | 25% | ¥149.75 |
| 完整代理 | 20% | 按成功回款分成（订单基础价 0） |

**API 端点**

- 物业 admin（`/api/v1/admin/`）：
  - `GET legal-packages` — 服务包目录（租户视角，含平台默认 + 本租户覆盖）
  - `GET cases/{id}/legal-conversion-preview` — Dry-run 预览（时间线 + 推荐方案 + 4 包成本预估）
  - `POST cases/{id}/convert-to-legal` — 创建订单；同案件 active 订单去重 409
  - `GET legal-conversion-orders` / `GET {id}` / `POST {id}/cancel`
  - `GET legal-document-templates` / `GET {id}/document` / `POST {id}/document` / `GET {id}/document/versions`
- 平台 ops（`/api/v1/ops/`）：
  - `*` law-firms CRUD + 嵌套 lawyers add/patch/remove；执业证号 unique 冲突 409
- 平台 ops（`/api/v1/legal-workstation/`）：
  - `GET orders?law_firm_id=&status=` — 法务工作台筛选订单
  - `POST orders/{id}/start` — `dispatched → in_service`
  - `POST {admin}/{id}/dispatch` 在 admin 路径下接受 `law_firm_id` 优先 / `assigned_law_firm` free-text 回落；律师必须属该律所且 active
  - `POST {admin}/{id}/complete` — 完成时自增 `law_firm.completed_orders`
  - `GET firms/{id}/stats` — 含 `platform_fee_total_completed` + `platform_fee_unpaid`
  - 账单：`POST/GET firms/{id}/invoices` + `POST invoices/{id}/{confirm,paid,cancel}`

**关键不变量**

- `legal_conversion_order.platform_fee_amount` 在订单创建时按 `package.price × package.platform_fee_rate` 冻结；后续律所池或服务包配置变更不影响进行中的订单
- `dispatch` 时 denormalize 律所/律师姓名快照到订单 `assigned_law_firm` / `assigned_lawyer_name` 字段，便于审计追溯（即使律所/律师后续被停用或改名，订单历史不丢失）
- 订单 `complete` 时律所 `completed_orders` 计数 +1；账单按 `completed_at` 落入对应账期，与状态机一致
- 文书模板按 `(tenant_id, package_type)` 二级查找：租户级模板优先 → 平台默认兜底；缺失占位填 `[未填]` 而非崩溃
- 业务事务与通知发送解耦：通知发送失败做 log，不回滚业务（dispatcher 内 try/except）

#### 20.4.2 v1.6.8 — 两步审批流（催收员申请 → 督导/admin 审批）

v1.5 admin 直接 `POST cases/{id}/convert-to-legal` 一步建单的能力**保留不动**；新增**平行的申请通道**让催收员主动上报。

```
催收员通话/跟进后 → 点「申请转法务」+ 写理由
    ↓ POST /agent/cases/{id}/intent action=transfer_legal
    ↓ INSERT legal_conversion_request(status='pending', reason=...)
督导/admin 在「法务转化审批」inbox 看到申请
    ↓ POST /legal-conversion-requests/{id}/approve {package_id, notes}
    ↓ 复用 build_legal_conversion_order helper → 创建 LegalConversionOrder
    ↓ 申请单 status='approved' + related_order_id
    OR
    ↓ POST /legal-conversion-requests/{id}/reject {reason}  // 必填
    ↓ status='rejected' + reviewer_note
```

**新数据模型 `legal_conversion_request`**（迁移 24009v168）：
- 字段：`tenant_id / case_id / requester_user_id / requester_role / reason / status / reviewer_user_id / reviewer_role / reviewed_at / reviewer_note / related_order_id`
- 状态：`pending | approved | rejected | cancelled`
- 同 case 已有 active LegalConversionOrder 或 pending request → 重复申请 409

**审批端点角色**：`supervisor / admin / platform_super`（VIEWER_ROLES 还包含 agent_* 但只能看自己提交的）

**为什么不直接让 admin 一步建单足够**：实测中催收员是最早判断"业主不可能自愿缴"的人，但他们没有合规判断能力（哪些案件适合走法务、买哪个服务包）。两步流程让前线发起 + 后端把关，既不浪费催收员的判断力，又确保法务订单符合公司风控策略（v1.6.8 决策详见 §22.2）。

#### 20.4.3 v0.5.5 — 服务包定价归属与 OPS 后台维护

法务服务包是**平台级目录**（`legal_service_package.tenant_id IS NULL`），4 档（律师函 / 诉前调解 / 小额诉讼 / 完整代理）对所有物业租户统一公开，**不存在租户专属价**。

**定价归属链**：

```
律所提交承接价 → 平台 OPS 在「服务包目录」后台维护 → 全租户公开同价
    ↑                                          ↓
    └──── 律所抽佣账期由 platform_fee_rate 决定 ←┘
```

| 主体 | 角色 | 职责 |
|---|---|---|
| 律所 | 服务提供方 | 给 4 档报最低承接价（行业惯例 ¥800/1800/3200/4800） |
| 平台 OPS | 目录维护者 | 在 `/ops/legal-packages` 在线改 `price` / `description` / `platform_fee_rate` / `enabled` / `sort_order` |
| 物业 admin / 督导 / 催收员 / 法务对接人 | 采购方 / 知情方 | 看到 OPS 维护的统一价（不议价、不下浮） |

**OPS 后台能力**（`/api/v1/ops/legal-packages`）：

- `GET legal-packages` — 列出全平台 4 档（含 disabled，按 sort_order 排序）
- `PATCH legal-packages/{id}` — 改 `price / platform_fee_rate / description / enabled / sort_order / name`；守卫 `require_roles("ops","superadmin")`；每次改动写 `AuditLog(action='ops.legal_package.patched', payload={changes, package_slug})`
- 范围最小化：**不允许新增/删除包**，包目录由产品 + 数据迁移确定；**不允许租户专属价**，未来扩展需走迁移

**已下单订单价格冻结原则**（v1.5 起的关键不变量，本次强化）：

- 订单创建时按 `package.price × package.platform_fee_rate` 冻结 `price_quoted` + `platform_fee_amount` 到 `LegalConversionOrder` 行
- OPS 后台改价**只影响新下单**，进行中订单的报价不变
- 详情页（`/admin/legal-conversion/{id}`）拆分展示：「律所承接价 ¥X + 平台服务费 ¥Y（N%）= ¥总价」+ 小字注明「由平台 OPS 统一维护」

**详情页业主信息卡**（v0.5.5 同步加）：

- 后端 `GET /admin/legal-conversion-orders/{id}` 返回 `owner_name / owner_room / owner_phone_masked / project_name / package_description / package_platform_fee_rate`
- 前端详情页顶部「业主信息卡」展示业主姓名 / 房号 / 项目名 / 手机号脱敏 + 关联案件链接，替代原孤立的「案件 #ID」冷编号

**单元 / 集成测试覆盖**

- service：推荐分级（金额阶梯）、时间线聚合（通话历史 group_by）、成本预估（含小额诉讼受理费）、模板渲染（占位替换 + 缺省回落 + 租户覆盖）
- API 状态机：dispatch 拒绝停用律所 / 跨律所律师；同案件去重 409；admin 不能 dispatch（403）；订单完成更新律所计数；账单 confirm/paid/cancel 状态机；账单生成幂等
- 数据安全：跨租户 404；ops vs admin 角色边界

---

### 20.5 数据洞察产品（v2.0）

平台积累足够用户量（≥ 50 家物业公司 / ≥ 10 万通话记录）后，脱敏数据具备商业价值：

**行业基准报告（B2B 销售）**
- 全国/分城市 物业费催收转化率基准
- 业主异议类型分布（质量投诉 / 经济困难 / 服务不满 占比趋势）
- 催收最佳实践：最优通话时段 / 最有效话术类别 / 承诺跟进最优间隔

**购买方**：物业协会 / 咨询公司 / 催收行业研究机构  
**定价**：¥5,000-50,000/份（按覆盖范围）

**物业公司自身对标服务（SaaS 增值）**
- "您的催收转化率比同城同规模物业低 12%，主要差距在…"
- 专业版以上附赠基础对标，企业版包含深度对标报告

---

### 20.6 白标/OEM 授权（v1.1+）

**目标**：借助现有物业 SaaS 厂商的客户渠道快速扩量，无需自建销售团队。

**合作形式**

| 形式 | 说明 | 收费模式 |
|------|------|---------|
| API 接入 | 物业 SaaS 厂商将 AI 通话辅助模块嵌入自身产品 | 按 API 调用量收费（元/分钟）|
| 白标部署 | 整套系统更换品牌 logo，部署在合作方基础设施上 | 年授权费 + 维护费 |
| 联合方案 | 双方联合销售，共同打包方案报价 | 收入分成（平台方 40-60%）|

**潜在合作方**：万商云集、云智慧、天行健、物管家等物业 SaaS 厂商，以及银行/金融机构的早期催收业务线。

---

### 20.7 垂直行业扩展（v2.0+）

物业催收是起点，产品逻辑复用率 > 80%，可依次扩展：

| 行业 | 场景 | 复用度 | 备注 |
|------|------|--------|------|
| 商业地产 | 写字楼/商铺租金催缴 | 90% | 客单价更高 |
| 长租公寓 | 租金欠费 + 押金纠纷 | 85% | 用户量大 |
| 公用事业 | 水费/燃气欠费（TO G）| 70% | 政府采购周期长 |
| 银行消金 | 信用卡/小额贷款早期催收 | 60% | 监管要求更严，需专项合规 |

扩展策略：先打透物业，建立行业口碑和数据积累，再以"有证·XX 催"子品牌横向扩展（有证慧催 → 有证商催 → 有证租催）。

---

### 20.8 商业模式路线图

```
阶段一（0-12 个月）：打磨工具，跑通单一客户
  收入来源：SaaS 订阅（基础版 / 专业版）
  目标：20 家付费物业公司，ARR ¥200 万

阶段二（12-36 个月）：平台化，打开增量收入
  收入来源：+ 服务商撮合抽佣 + 合规存证按需服务 + 法务转化通道
  目标：100 家物业公司 / 30 家服务商，ARR ¥1,000 万

阶段三（36+ 个月）：数据 + 生态
  收入来源：+ 行业数据报告 + 白标授权 + 垂直行业扩展
  目标：成为物业催收行业标准工具，ARR ¥5,000 万+
```

---

## 21. 页面交付清单（按角色）

> 本节是 UI 设计和开发的直接输入。共 **11 个角色**（租户侧 6 个 + 项目负责人（两侧）+ 服务商管理员 + 平台超管 + 平台运营员），每个角色列出所有页面、核心操作和明确的排除项。

---

### 角色总览

| # | 角色 | 标识 | 终端 | 归属层 |
|---|------|------|------|--------|
| 1 | 平台超管 | `platform_superadmin` | PC（独立后台）| 平台运营方 |
| 2 | 平台运营员 | `platform_ops` | PC（独立后台）| 平台运营方 |
| 3 | 服务商管理员 | `provider_admin` | PC | 服务商 |
| 4 | 物业公司管理员 | `admin` | PC | 租户 |
| 5 | 主管/督导 | `supervisor` | PC | 租户 |
| 6 | 内部催收员 | `agent_internal` | PC + App | 租户 |
| 7 | 外部兼职催收员 | `agent_external` | **仅 App** | 租户/服务商 |
| 8 | 法务专员 | `legal` | PC | 租户/服务商 |
| 9 | 工单处理员 | `workorder` | PC | 租户 |
| 10 | 项目负责人（物业侧） | `project_manager_property` | PC | 租户 |
| 11 | 项目负责人（服务商侧） | `project_manager_provider` | PC | 服务商 |

---

### 角色 1：平台超管（platform_superadmin）

> 有证慧催技术/安全负责人，负责底层系统配置和安全审计，**不参与日常开通/审核等业务操作**。人数极少（1-2 人），建议强制 MFA 登录。

**访问入口**：`admin.youcuihuicui.com`（独立域名，IP 白名单限制）

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 1.1 | **系统健康监控** | 服务状态（ASR/LLM/WebSocket/数据库可用率）；接口响应时间 P90；错误率告警；区块链存证成功率 | P0 |
| 1.2 | **平台运营员账号管理** | 创建/停用平台运营员账号；设置权限范围（可操作哪些租户）；平台内部人员列表 | P0 |
| 1.3 | **套餐配置** | 定义/修改订阅套餐（名称/月费/用户上限/案件上限/功能模块开关）| P0 |
| 1.4 | **LLM 基础 Prompt 管理** | base_prompt 版本列表；创建/编辑草稿；发布/回滚；A/B 测试配置与效果（v1.1）| P1 |
| 1.5 | **全局风控关键词** | 平台级敏感词增删改查；分类管理（业主辱骂/威胁/员工违规）；对所有租户生效 | P0 |
| 1.6 | **App 版本管理** | 上传新版 APK；配置最低兼容版本（低于此版本强制更新）；灰度发布配置；版本发布历史 | P0 |
| 1.7 | **区块链存证配置** | 链上合作方选择（蚂蚁链/至信链）；API 密钥管理；存证异常告警（v1.1）| P1 |
| 1.8 | **平台审计日志** | 所有平台层操作记录（超管+运营员）；操作人/时间/内容/IP；不可删除；支持条件导出 | P0 |
| 1.9 | **数据库与存储管理** | 备份状态监控；存储用量告警；数据保留策略执行情况（仅查看，操作在运维层）| P1 |
| 1.★ | **成本看板** | 全平台通话分钟池总量/已用/剩余；各租户本月消耗排名（按通话分钟从高到低）；近6个月成本趋势折线图（含通话费用）；超配预警阈值提示 | P0 |

**明确排除**：不参与租户开通/停用/续费等业务操作（交给运营员）；不能查看任何租户内部通话录音或业主数据；不能直接操作租户侧案件。

---

### 角色 2：平台运营员（platform_ops）

> 有证慧催的销售支持/客户成功/运营人员，负责日常客户管理：开通租户、审核服务商、跟进续费、处理客户支持请求。**不能修改任何系统技术配置**。每位运营员只能看到和操作**自己负责（已分配）的租户和服务商**，由超管在「平台运营员账号管理」（页面 1.2）中配置分配关系。

**访问入口**：同 `admin.youcuihuicui.com`，与超管共用后台，但菜单范围不同

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 2.1 | **运营数据大盘** | 自己负责客户的业务 KPI：活跃租户数/本月新增/续费率/试用转化率；到期预警（30天内到期的我的租户列表）| P0 |
| 2.2 | **租户列表** | 自己负责的物业公司列表；多维筛选（套餐/状态/到期日）；快捷操作入口 | P0 |
| 2.3 | **租户详情** | 基本信息（公司名/信用代码/管理员手机）；订阅套餐与有效期；当前用量（用户数/案件数/本月通话分钟/已用配额占比）；**调整通话分钟配额**（modal：新配额值、生效时间选择（立即/下月）、变更记录日志）；签约服务商；跟进记录时间线 | P0 |
| 2.4 | **开通新租户** | 表单：公司名/统一社会信用代码/管理员姓名+手机/套餐/有效期/最大用户数；提交后自动发短信激活；一键开通 14 天试用 | P0 |
| 2.5 | **租户续费/变更套餐** | 延长有效期；升降套餐；修改用户数上限；操作记录自动存入跟进时间线 | P0 |
| 2.6 | **租户停用/恢复** | 停用账号（租户数据保留，用户无法登录）；恢复操作；停用原因记录 | P0 |
| 2.7 | **试用账号跟进** | 试用中租户列表；剩余天数；使用活跃度（登录次数/通话次数）；是否已联系；标记跟进状态（已联系/待签约/已放弃）| P0 |
| 2.8 | **服务商列表** | 自己负责的服务商；状态（审核中/已激活/已停用）；筛选（类型/签约租户数/注册时间）| P0 |
| 2.9 | **服务商审核** | 待审核申请详情：服务商名称/类型/营业执照图片/联系人；操作：通过/拒绝（填写拒绝原因）；通过后自动发短信通知 | P0 |
| 2.10 | **服务商详情** | 基本信息；签约租户列表；团队成员数；操作：停用/恢复 | P0 |
| 2.11 | **全平台结算总览** | 各租户→服务商月度结算状态（已付/未付/逾期）；平台服务费收入汇总；逾期超 30 天的告警 | P1 |
| 2.12 | **客户跟进记录** | 为每个租户记录跟进备注（电话沟通/邮件/拜访）；查看历史跟进时间线；设置下次跟进提醒 | P1 |
| 2.13 | **系统公告管理** | 创建/编辑公告（内容/目标受众/发布时间）；定时发布；查看已发布历史；支持指定租户或全量发送 | P1 |
| 2.14 | **运营员操作日志（本人）** | 查看自己的操作历史（不能查看其他运营员，完整日志由超管审计）| P1 |

**明确排除**：不能查看或操作未分配给自己的租户和服务商；不能修改套餐定价；不能修改 LLM Prompt 或全局风控词；不能查看任何租户内部通话录音或业主数据；不能查看平台技术监控；不能删除任何数据；不能操作其他运营员的账号。

---

### 角色 3：服务商管理员（provider_admin）

> 律所或兼职催收团队的负责人，管理本团队成员，查看各签约物业公司的工作和收益。

**访问入口**：PC 端主站登录后进入服务商工作空间

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 2.1 | **服务商概览** | 签约物业公司数、本月完成通话数、**本月通话分钟（已用）**、本月应收金额、团队成员数；各客户待处理事项入口 | P0 |
| 2.2 | **团队成员管理** | 成员列表（姓名/角色/状态）；新增成员（内部员工直接创建）；停用/恢复账号；查看各成员当前分配情况 | P0 |
| 2.3 | **合约管理** | 与各物业公司的合约列表（到期日/计费方式/状态）；查看合约详情；接受/拒绝物业公司邀请（v1.1）| P0 |
| 2.4 | **应收账款** | 各客户本月/历史结算单；状态（草稿/已确认/已付款/异议中）；导出 Excel/PDF 账单 | P0 |
| 2.5 | **成员绩效汇总** | 各成员在各客户公司的：通话量/承诺量/转化量/绩效积分；跨客户合并视图 | P1 |
| 2.6 | **成员个人佣金** | 每位成员的月度佣金明细（回款金额×比例+积分奖金-违规扣款）；用于内部薪酬核算 | P1 |
| 2.7 | **结算异议提交** | 对有争议的结算单填写异议说明并提交；追踪异议处理状态 | P1 |

**明确排除**：不能看到其他服务商的任何信息；不能跨租户查看（A 物业的案件对 B 物业不可见）；不能修改任何物业公司的系统配置。

---

### 角色 4：物业公司管理员（admin）

> 物业公司的系统负责人，掌管全公司数据、配置、人员和结算。

**访问入口**：PC 端主站（`app.youcuihuicui.com`）

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 3.1 | **管理看板首页** | 今日外呼量/接通量/承诺缴费数/回款金额；**本月通话分钟（已用/配额/剩余，用量超过80%时橙色警示）**；全员排名；公海案件数；AI 话术采用率趋势；风控告警摘要 | P0 |
| 3.2 | **CRM 案件列表** | 全公司所有案件；多条件筛选（员工/阶段/欠费金额/楼栋/时间）；批量操作（批量分配/批量标记）| P0 |
| 3.3 | **CRM 案件看板** | 按阶段看板：待联系/跟进中/承诺缴费/已缴费/升级中/已关闭 | P0 |
| 3.4 | **案件详情页** | 业主信息+欠费明细（左侧）；活动时间线：历次通话摘要+AI分析+跟进备注+状态变更（右侧）；操作按钮：分配/转法务/建工单 | P0 |
| 3.5 | **公海管理** | 公海列表（欠费等级/优先级排序）；手动分配给员工；各员工私海数量概览；释放规则状态 | P0 |
| 3.6 | **业主名单导入** | Excel/CSV 上传；字段映射预览；重复检测；导入结果报告 | P0 |
| 3.7 | **录音批量上传** | 拖拽上传多个录音文件；实时进度；分析完成后查看结果列表（筛选/导出）| P0 |
| 3.8 | **用户管理** | 员工列表；新建内部员工（姓名/手机/角色/所属主管）；邀请外部兼职（生成链接，设配额/到期日/时段）；停用/恢复；批量 Excel 导入员工 | P0 |
| 3.9 | **服务商合作管理** | 签约服务商列表；邀请新服务商；查看各服务商成员在本公司的权限配置；调整配额/到期日 | P1 |
| 3.10 | **结算管理** | 各服务商月度结算单列表；查看明细；确认结算单；上传付款凭证；标记已付款；查看历史付款记录 | P0 |
| 3.11 | **话术库管理** | 话术条目 CRUD；Excel 导入；启用/禁用；效果看板（采用率/转化率/综合评分）；版本历史回滚 | P1 |
| 3.12 | **数据报表** | 转化漏斗趋势；员工效率对比；异议类型分布；承诺跟进完成率；可设时间范围 | P1 |
| 3.13 | **合规月报** | 查看/下载当月合规催收行为月报 PDF；查看历史月报列表 | P1 |
| 3.14 | **系统配置** | 录音模式（实时/事后/自动降级）；L3 挂断开关；联系频次上限；AI 推送灵敏度；风控自定义词；数据保留期 | P1 |

**明确排除**：不能查看其他租户的任何数据；不能修改平台级配置（Prompt/全局词库）。

---

### 角色 5：主管/督导（supervisor）

> 管理本组催收员，质检复核，接收升级案件。

**访问入口**：PC 端主站（与管理员相同入口，菜单范围收窄）

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 4.1 | **督导工作台首页** | 待复核通话数；本组今日绩效摘要；升级至我的案件数；**本月团队通话分钟用量趋势（已用总量+近7日柱状图）**；风控告警（本组）| P0 |
| 4.2 | **CRM 案件列表（本组）** | 仅显示本组员工的案件；筛选/搜索；可手动接管任意案件 | P0 |
| 4.3 | **案件详情页** | 同管理员，但只能看到本组案件 | P0 |
| 4.4 | **质检复核工作台** | AI 标记的 needs_review 通话列表；录音播放器（支持跳转到风控时间点）；修改 AI 标签；打标（优质/差/需改进）；填写改进建议 | P0 |
| 4.5 | **升级案件处理** | 从催收员升级上来的大额/疑难案件；查看全部历史通话摘要；记录协商进展（分期协议等）；可再次升级到法务 | P0 |
| 4.6 | **风控事件记录** | 本组所有风控事件时间线；点击跳转对应录音时间点；可对 L2/L3 事件添加处置备注 | P1 |
| 4.7 | **团队绩效** | 本组成员排名；各成员通话量/承诺数/转化率；与上期对比 | P1 |

**明确排除**：不能看到其他组数据；不能修改系统配置；不能查看结算/财务数据；不能生成邀请链接。

---

### 角色 6：内部催收员（agent_internal）

> 正式员工，主要使用 App 外呼，PC 端看自己的案件和数据。

#### 6A — Android App 页面

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 5A.1 | **今日任务列表（首页）** | 私海案件列表，按优先级排序（欠费金额/逾期月数）；状态筛选（待联系/跟进中/承诺中）；今日完成数角标；**本月通话分钟小卡（已用/配额，进度条）** | P0 |
| 5A.2 | **公海浏览** | 公海案件列表（脱敏预览）；一键认领（有配额上限）；认领后进入私海 | P0 |
| 5A.3 | **拨号前业主预览** | 点击案件后查看：姓名+房号+欠费金额+欠费月数+历史通话摘要；底部「立即拨打」按钮 | P1 |
| 5A.4 | **实时通话界面** | 顶部：通话控制栏（时长/挂断/静音）；中部：业主基本信息 + ASR 实时对话滚动；底部：AI 话术建议卡片（采用/忽略）；浮动：支付二维码按钮、建工单按钮 | P0 |
| 5A.5 | **通话后标记弹窗** | 挂机后自动弹出；AI 预填结果（意图/备注）；员工确认/修改；一键提交 | P0 |
| 5A.6 | **支付二维码全屏** | 业主专属大图二维码（含欠费金额+物业信息）；可截图发微信 | P0 |
| 5A.7 | **今日绩效小结** | 今日外呼次数/有效通话/承诺数/绩效积分；本月累计积分和佣金预估 | P1 |
| 5A.8 | **个人设置** | 修改密码；头像；通知设置 | P1 |

#### 6B — PC 端页面

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 5B.1 | **我的案件列表** | 仅自己私海案件；筛选/搜索；点击案件名或「拨打」触发 DIAL_REQUEST 到 App | P0 |
| 5B.2 | **案件详情页** | 业主信息+欠费详情；活动时间线（仅本人操作）；操作：建工单/转主管/转法务 | P0 |
| 5B.3 | **实时通话工作台（自动弹出）** | 通话发起后自动展开；左：业主信息；中：ASR 实时对话；右：AI 建议+快捷操作（发二维码/建工单/转接）| P0 |
| 5B.4 | **个人绩效** | 本月通话量/转化率/排名位次（全公司排名，只显示自己的位置，不显示他人数据）；**本月通话分钟（已用/配额）** | P1 |

**明确排除**：不能看到其他员工的案件；不能修改公海规则或系统配置；不能导出他人数据。

---

### 角色 7：外部兼职催收员（agent_external）

> 合同制/兼职，**仅限 App**，受限账号，全程号码脱敏，禁止导出。

#### App 页面（App only，无 PC 入口）

| # | 页面 | 核心功能 | 差异（vs 内部催收员）| 优先级 |
|---|------|---------|-------------------|--------|
| 6.1 | **今日任务列表** | 同 5A.1 | 上限 10 条；手机号始终脱敏 | P0 |
| 6.2 | **公海浏览** | 同 5A.2 | 配额上限 10 条（管理员配置）；仅能认领，不能释放到主管 | P0 |
| 6.3 | **实时通话界面** | 同 5A.4 | 手机号脱敏；AI 建议正常显示；**无建工单按钮**；**无转法务按钮** | P0 |
| 6.4 | **通话后标记弹窗** | 同 5A.5 | 无法看到完整号码 | P0 |
| 6.5 | **支付二维码** | 同 5A.6 | 无差异 | P0 |
| 6.6 | **个人设置** | 同 5A.8 | 无差异 | P1 |

**明确排除**：无 PC 端登录权限；无任何数据导出功能；无「转法务」操作；不能查看完整手机号；不能查看其他兼职的案件。

---

### 角色 8：法务专员（legal）

> 处理升级至法务追诉阶段的案件，不接触日常催收数据。

**访问入口**：PC 端主站（菜单仅显示法务相关模块）

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 7.1 | **法务案件队列** | 分配给本人的法务案件列表；状态筛选（待处理/律师函已发/立案中/结案）；按欠费金额/逾期时间排序 | P0 |
| 7.2 | **法务案件详情** | 案件基本信息 + 欠费详情；历次催收通话摘要（ASR 关键段落，不需要听录音）；已上传的法务文件列表；进展时间线 | P0 |
| 7.3 | **进展更新** | 记录法务处理步骤：律师函已发 / 已送达 / 诉前调解 / 立案 / 开庭 / 判决 / 执行；每步可上传附件（函件/裁定书）| P0 |
| 7.4 | **存证包下载** | 为当前案件导出完整存证包（录音+转写+AI记录+区块链证明）；一键打包下载 ZIP | P1 |
| 7.5 | **文件管理** | 案件相关法律文件上传/查看/删除；按文件类型分类 | P1 |

**明确排除**：不能看到非分配给自己的案件；不能查看公海/私海；不能修改催收员数据；不能访问结算或话术模块。

---

### 角色 9：工单处理员（workorder）

> 处理催收通话中产生的物业问题工单（漏水/电梯故障/投诉等），不接触催收数据。

**访问入口**：PC 端主站（菜单仅显示工单相关模块）

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 8.1 | **工单列表** | 待处理 / 处理中 / 已完成三列；按紧急程度排序；支持按类型筛选（漏水/停电/电梯/投诉）| P0 |
| 8.2 | **工单详情** | 工单基本信息（房号/问题描述）；AI 从通话中提取的业主原话摘要；历史处理记录；操作按钮 | P0 |
| 8.3 | **工单处理** | 更新状态（接单/处理中/已完成）；填写处理结果和备注；系统自动通知对应催收员工单已处理 | P0 |
| 8.4 | **历史工单查询** | 搜索已完结工单；按时间/类型/房号查询 | P1 |

**明确排除**：不能查看通话录音或完整转写；不能查看业主欠费信息；不能查看手机号；不能访问任何催收、法务、结算模块。

---

### 角色 10/11：项目负责人（project_manager）

> 项目负责人是**项目级只读管理角色**，物业公司和服务商各自任命一名，负责跟进单个催收/外呼项目的整体进展。两侧使用同一 UI 模板（`project-manager.html`），但数据范围限定在被指派的项目内。
>
> - **物业侧项目负责人**（`project_manager_property`）：由物业公司管理员在「项目管理」页指派，只能查看本物业公司下该项目的数据。
> - **服务商侧项目负责人**（`project_manager_provider`）：由服务商管理员在「项目列表」页指派，只能查看本服务商承接的该项目的数据。
>
> 两侧负责人看到的数据是同一项目的同一套数据（统计口径一致），仅有归属标签不同。

**访问入口**：`app.youcuihuicui.com`（与其他租户/服务商角色共用，菜单仅显示项目相关模块）

| # | 页面 | 核心功能 | 优先级 |
|---|------|---------|--------|
| 10.1 | **项目总览** | 项目 KPI（案件总数/已回款数量与金额/本月接通率/转工单数/转法务数）；回款进度分布（按欠款金额段）；近30天日回款趋势图；快速跳转到工单/法务/案件列表 | P0 |
| 10.2 | **案件进展** | 项目范围内所有案件列表（业主/欠款/催收员/状态/最近联系时间）；支持按状态/金额段筛选；支持导出 Excel；只读，不可修改案件分配 | P0 |
| 10.3 | **工单情况** | 项目范围内所有工单列表（工单编号/类型/摘要/状态/负责人）；工单状态分布图；支持按状态/类型筛选；只读，不可操作工单 | P0 |
| 10.4 | **法务进度** | 项目范围内所有法务案件（阶段/涉案金额/律师/下次关键节点）；阶段分布与涉案金额汇总；支持导出 Excel；只读，不可修改法务案件 | P0 |

**明确排除**：
- 不能查看通话录音、转写内容
- 不能访问用户管理、话术库、系统配置、结算模块
- 不能指定服务商或修改项目与服务商的关联关系（物业侧不能指定服务商；服务商侧不能修改合约条款）
- 不能查看其他项目的数据（只能看被指派的项目）
- 不能对案件、工单、法务案件做任何修改操作

---

### 页面数量汇总

| # | 角色 | 归属层 | PC 页面 | App 页面 | 合计 |
|---|------|--------|---------|---------|------|
| 1 | 平台超管 | 平台 | 9+1（成本看板）| — | 10 |
| 2 | 平台运营员 | 平台 | 14 | — | 14 |
| 3 | 服务商管理员 | 服务商 | 7+1 | — | 8 |
| 4 | 物业公司管理员 | 租户 | 14+1 | — | 15 |
| 5 | 主管/督导 | 租户 | 7 | — | 7 |
| 6 | 内部催收员 | 租户 | 4 | 8 | 12 |
| 7 | 外部兼职催收员 | 租户/服务商 | — | 6 | 6 |
| 8 | 法务专员 | 租户/服务商 | 5 | — | 5 |
| 9 | 工单处理员 | 租户 | 4 | — | 4 |
| 10/11 | 项目负责人（两侧共用模板） | 租户/服务商 | 4 | — | 4 |
| — | **合计** | | **69** | **14** | **83** |

**MVP P0 页面约 51 个**，P1 页面（约 32 个）在 v1.1 交付。其中角色 3/4 新增 +1 页为「项目列表」管理页（内嵌于各自后台），角色 10/11 共用 `project-manager.html` 4 页，角色 1 新增 +1 页为「成本看板」（通话分钟池总量/成本趋势，P0）。

### 平台后台与租户端入口隔离

```
admin.youcuihuicui.com     ← 平台超管 + 平台运营员（独立域名，IP 白名单）
app.youcuihuicui.com       ← 租户侧所有角色（物业公司管理员/主管/催收员/法务/工单）
                              服务商管理员登录后自动路由到服务商工作空间
```

两个入口共用同一套后端 API，通过 JWT 中的 `role` 和 `scope`（`platform` / `tenant:{id}` / `provider:{id}`）做权限隔离。

---

## 22. 决策日志（v1.5.7 - v1.6.10）

> **目的**：记录 v1.5.7 - v1.6.10 期间针对核心业务流程做出的关键产品决策，包含「背景动机 / 决策内容 / 思考过程 / 影响范围」。便于后续团队理解某条规则为何如此设计，避免相同的争论再次发生。每条决策对应一次实测发现的问题或一次产品讨论。

### 22.1 公海池主动抢单 + 持有上限（v1.6.9）

**背景**：MVP 设计是"管理员手动分配 + 催收员被动接单"。实测发现：
- 物业体量小，admin 每天分配几十条案件成为瓶颈
- 催收员能力差异大，"快手" 1 天能跟 30 条，"慢手" 跟 5 条都吃力
- 等管理员分配的延迟让高优先级案件错过最佳追讨窗口

**决定**（已实现，详见 §13.7）：
- 催收员可在「我的案件 → 公海池」主动抢单（claim）
- 持有上限由 `tenant_settings.public_pool_claim_max` 控制（默认 50，CHECK 1-1000）
- 自己持有的未结案案件可主动 release 放回公海

**思考过程**：
- ❌ 备选方案 A「无上限抢单」：被否决 — 快手会把整个公海抢空，团队负载严重不均
- ❌ 备选方案 B「保留纯管理员分配」：被否决 — admin 瓶颈未解
- ✅ 当前方案「抢单 + 上限」：保留管理员分配（仍是主路径），抢单是补充通道；上限确保团队整体负载可控
- 上限默认 50 是经验值（团队 1 个内勤大约持 30-40 条比较合理，留 10-20 缓冲）；admin 可在系统配置调整

**影响范围**：
- 后端：`tenant_settings.public_pool_claim_max` 新字段 + 迁移 `24010v169`；3 个新 API（`/agent/me/pool-quota`、`/agent/cases/{id}/claim`、`/agent/cases/{id}/release`）；audit log 新事件 `case.claimed` / `case.released`
- 前端：「我的案件」加 tab 切换 + 抢单按钮 + 持有数量进度条
- 测试：4 个新 pytest（quota 默认值 / 上限阻断 / release own / release others 403）

---

### 22.2 法务转化两步审批（v1.6.8）

**背景**：v1.5 `POST /admin/cases/{id}/convert-to-legal` 让 admin 一步建单。但实测发现：
- 催收员是最早判断"业主不可能自愿缴"的人（直接通话感知）
- admin 远离一线，对每个案件是否值得走法务缺乏直觉
- 让催收员直接建法务单 → 风控失控（什么单都转，律所收到一堆低价值单）

**决定**（已实现，详见 §20.4.2）：保留 admin 直接建单 + 平行新增"催收员申请 + 督导/admin 审批"通道。两条路径不互斥。

**思考过程**：
- ❌ 备选方案 A「让催收员直接建单」：被否决 — 风控失控
- ❌ 备选方案 B「废弃 admin 一步建单只走审批」：被否决 — admin 在某些场景（如批量历史欠费导入后立即转法务）需要快速建单能力
- ✅ 当前方案「两条路径」：催收员发起 + 督导把关是常规路径；admin 一步建单是兜底

**为什么用独立 `LegalConversionRequest` 表而不是给 `LegalConversionOrder` 加 `awaiting_approval` 状态**：Order 的状态机本来就是「已建单 → 派发 → 服务 → 完成」的法律业务流；混入"审批中"会让 Order 同时承担"未确定要不要建"和"已建已派单"两种语义，命名/查询/列表渲染都难做。独立表更干净。

**影响范围**：
- 后端：新表 `legal_conversion_request` + 迁移 `24009v168`；3 个新 API（list/approve/reject）；admin endpoint 抽出 `build_legal_conversion_order` helper 给两个路径共用
- 前端：督导侧新页 `/supervisor/legal-conversion-approvals`；`ConvertToLegalModal` 加 `mode='approve'`；催收员申请按钮在工作台 + 详情页双入口
- 测试：9 个新 pytest

---

### 22.3 案件详情页统一蓝本（v1.6.9 - v1.6.10）

**背景**：admin/agent/supervisor 三个角色各有独立的 detail.tsx，维护负担大且 UI 不一致：
- supervisor 的 detail.tsx 757 行，自建 ProjectInfoCard、BillBreakdownCard、WorkOrdersCard
- admin/agent 用了部分共享组件但 BillBreakdownCard 重复写
- 用户实测：「6 个入口（admin 案件列表、agent 我的案件、supervisor 案件分配、升级处理、承诺催付、超期预警）的 详情页 应该统一」

**决定**：
- **后端**：`build_case_detail_response` helper 三角色共用（admin/agent/supervisor 三个 GET endpoint 同源返回 `CaseDetailResponse`）
- **前端蓝本**：左栏「业主信息卡（含累计欠费 + 账单期 + 三栏金额拆分 + 欠费理由）」+「项目情况卡」/ 中栏「活动时间线」+「添加跟进备注」/ 右栏 sticky「按角色显示的操作按钮」
- **共享组件**：`OwnerInfoCard / ProjectInfoCard / ActivityTimeline / FollowUpNoteCard / DiscountRequestModal`
- **角色差异只在右栏操作面板**：admin 4 按钮 / agent 5-6 按钮 / supervisor 4-5 按钮

**思考过程**：
- ❌ 备选方案 A「保持三套独立页」：维护负担大，UI 不一致
- ❌ 备选方案 B「全统一为单组件按 role 显示不同操作」：被采纳的核心思路
- 关键发现：账单期 + 三栏金额本来就在 `OwnerInfoCard` 里实现了，但又额外写了一个 `BillBreakdownCard` 在底部 → 重复展示。**决策**：删 `BillBreakdownCard` 组件文件，账单一律走业主信息卡内嵌。

**影响范围**：
- 后端：`supervisor_case_detail.py` 156 行 → 9 行（复用 helper）；admin stage endpoint 角色扩展到 supervisor
- 前端：supervisor detail 757 行 → ~200 行；admin/agent/supervisor 三页骨架完全统一；删除 `BillBreakdownCard.tsx` + 新建 `FollowUpNoteCard.tsx`

---

### 22.4 时间线节点详情可点击 + 内联听录音（v1.6.9 - v1.6.10）

**背景**：v1.6.7 已经在通话节点加了 `<audio controls>` 内联播放，但只在 `recording_url` 存在且 `status=processed` 时才显示。用户测试时反映：
- 工单/法务/阶段变更等节点没有任何交互（只是文本）
- 录音播放控件不够明显（用户找不到）

**决定**：
- **TimelineEvent schema 加 `target_id` + `target_type`**：让前端按 type 跳详情（workorder→`/workorder/orders/{id}` / legal_order→`/admin/legal-conversion/{id}` / legal_case→`/legal/cases/{id}`）
- **通话节点加显式「🎧 听录音」按钮**：受控展开 audio（`autoPlay`），无录音时按钮 disabled 灰色
- **其他系统事件支持 expand**：长 note 点击展开 + 显示操作人 + ID

**思考过程**：交互不显式 → 用户根本不知道有这个能力。同样的功能加一个明确的按钮就解决了。无歧义，直接做。

**影响范围**：
- 后端：`schemas/case.py` `TimelineEvent` 加 2 字段；`services/case_timeline.py` 工单/法务/法务案件事件填 `target_id`
- 前端：`ActivityTimeline.tsx` 抽 `CallRow` 子组件，每行独立 `audioOpen` state；系统事件抽 `SystemEventRow`

---

### 22.5 多身份切换 + 督导兼任催收员（v1.6.9 - v1.6.10）

**背景**：原模型已支持「一人多 tenant」，但**未考虑「同一 tenant 内同一 user 多 role」**：
- 实际业务：督导经常需要直接打几个高优先级案件（教练手 / 救火）
- 律所代表也是律师本人 — 同一 user 兼任两个 role
- 用户实测：从督导切到催收员后，工作台业主画像消失、案件详情显示加载中

**决定**（已实现，详见 §3.2）：
- `UserTenantMembership` 已是 (user_id, tenant_id, role) 复合主键，本就支持多 role
- Topbar 切换角色时调 `queryClient.clear()` + `window.location.replace("/")` 清缓存
- demo seed `13000000003` 督导小李同时加 `agent_internal` membership + 分配 2 个案件演示

**重要 bug 与教训**：所有按 `user_id` + `tenant_id` 查 membership 的 SQL 默认假设单结果（`scalar_one_or_none()`），多 membership 后**直接 500**。修复方案是显式加 `role` 过滤 + `limit(1)`。这是数据模型早就支持但代码假设过窄的典型问题。**已在 §3.2 数据模型说明中明确写出该约束**。

**思考过程**：
- "一人一个角色"是绝大多数 SaaS 的简化假设；当业务真实需要多角色时，前端 + 后端都要审计每一个 membership 查询
- 切换体验上：原 `window.location.href = "/"` 在某些条件下被 React Router 拦截不真硬刷；改 `replace("/")` + `queryClient.clear()` 双保险

**影响范围**：
- 后端：`build_case_detail_response` 查 assigned 用户角色加 `role IN agent_*` 过滤 + limit(1)；assign 端点同样修
- 前端：`Topbar.handleSwitch` 注入 `useQueryClient().clear()`
- demo seed 演示数据

---

### 22.6 减免申请快捷按钮三角色共用（v1.6.9）

**背景**：减免申请之前埋在「督导 → 案件详情 → 谈判区」深路径，催收员在通话结束后想发起减免要切多个页面。

**决定**：
- 抽 `DiscountRequestModal` 共享组件（`components/discount/`）
- 三处入口：催收员案件详情右栏 + 工作台 col-4 quick-actions + 督导案件详情 + 督导升级处理页 ActionRow
- 后端 `POST /cases/{id}/discount-offers` 已支持催收员/督导双角色发起，按 `discount_pct` 自动判定走督导审批 / admin 审批 / 自动通过

**思考过程**：现成的后端能力前端没暴露。最少改动：写一个 Modal，挂到 5 个入口。

**影响范围**：
- 前端：新建 `DiscountRequestModal.tsx`；agent/supervisor 详情页 + agent 工作台 + supervisor escalated 页都接入

---

### 22.7 admin stage 端点角色扩展到 supervisor（v1.6.10）

**背景**：v1.6.10 督导详情页加跟进备注卡，需要 `PATCH stage` endpoint。新建 supervisor 专属端点 vs 复用 admin 端点的取舍。

**决定**：复用 `PATCH /admin/cases/{id}/stage`，把 `require_roles(*ADMIN_ROLES, "supervisor")` 加上 supervisor。

**思考过程**：
- ❌ 备选方案「新建 `PATCH /supervisor/cases/{id}/stage`」：复制粘贴一份 endpoint 代码，违反 DRY
- ✅ 当前方案：admin 与 supervisor 在租户范围内的 stage 写权限本就一致（督导是租户全权角色），扩 require_roles 是最小改动

**影响范围**：1 行代码改动（`admin_cases.py` `update_case_stage` 的 `require_roles`）；测试覆盖

---

### 22.8 v0.6.0 UX 大盘修复 — 13 反馈一波收口(2026-05-20)

**背景**:人工测试一次性反馈 13 个 UX / 产品问题,横跨 4 个角色(物业管理员/物业督导/催收员/项目经理)+ 公共修复 + 后端缺字段。用户决策:**一次性收口全做**(不分多版本),拆 5 个 Wave 串行(5-7 天,实际 4 天交付)。

**Wave A — 公共修复 + 物业管理员小修(`18938ff`)**
- 物业「分配/重分配」弹窗参考服务商风格改 RightDrawer 520px(`AdminAssignDrawer.tsx`,修「下拉只能看 2-3 个名字」)
- 残留 admin 字面量清查:减免 mock STATUS_LABELS / 律所升级 confirm / 排班说明等改「物业管理员」
- 业主名单导入修文件上传(原是纯视觉占位)— 加 ref input + 拖拽 + UTF-8 BOM 兼容 CSV 解析
- `settlement_statement.billing_method` 字段补齐 + 中文映射(三枚举)
- 法务转化订单页加「区块链存证」section + 后端端点

**Wave B — 督导工作流大重构(`d15b5b8`)**
- 案件详情「法务转化按钮」按 `pending_legal_conversion_request_id` 条件渲染(详 §4.4)
- 升级案件页:外层 4 按钮 → 2 按钮(介入处理 + 详情);介入处理弹窗 5 选项(亲自致电 / 陪同监听 / 标坏账 / 减免 / 转法务);后端 2 新端点 + alembic 加 `case.shadow_supervisor_id` + `case.close_reason`
- 承诺催付「催回访」改用 SupervisorCaseActionModal(走真实催办端点);移除「升级督导」按钮(语义错误,督导自己升级自己不通)
- 案件超期预警催办 / 重派 / 释放公海全部接通真实后端(新增 `POST /supervisor/cases/{id}/release-to-pool`)
- 风险事件 EventDetailModal 由只读改可写:select 处置类型 + textarea 处理结果;`risk_event.handle_status` 字段 + PATCH 端点扩展;handle_status='transferred_training' 联动 §22.10 培训库自动入库

**Wave C — 话术 AI 评分 + 培训案例库(`426a050`)**
- 话术 AI 评分:`script_template.ai_score / ai_score_updated_at / ai_score_sample_count` 字段 + asyncio loop 每 6h 重算 + 手动触发端点(算法见 §22.9)
- 前端 admin/scripts/effectiveness 表加「AI 评分」列(颜色分级 + ⚠ 样本不足提示);supervisor/script-labels 同步
- 培训案例库:新建 `training_case` 表 + 7 端点 CRUD(分页 / 手工入库 / 编辑 / view +1 / 删除);自动入库链路:督导处置风险事件 status=transferred_training → 后端 PATCH 联动 `from_risk_event()` 自动建训练案;asyncio 兜底 loop 每 24h 扫漏建
- 前端 training 页接通真实 API + 「手动入库」modal + category / source 双维度过滤;mock fallback 当后端 0 条

**Wave D — 催收员 + PM 提醒中心(`f80f245`)**
- 催收员工作台 KPI bar 下加「我的项目」横滚卡片条 — 按 project 分组:案件数 / 缴清数 / 已回款 / 预估佣金(按 work_mode 走 internal/external commission rate)
- 催收员 nav 新菜单「提醒中心」`/agent/reminders` — 整合 3 类软提醒(promise 72h / legal 状态变化 / case SLA 30d 停滞)+ 站内信(mark-read / read-all);后端 `/agent/me/reminders/synthetic`
- PM dashboard 顶部加「运营提醒」5 卡片网格(物业 + 服务商 PM 共用)— 审批积压 / 承诺逾期未催 / 坐席异常 / 成本预警 / 案件阶段停滞;5 分钟自动刷;count>0 整张卡片 Link 到 detail_path

**Wave E — PRD 文档同步(本提交)**
- §4.4 法务转化双路径 + 权限矩阵加「直接移交法务」越权权
- §8.2 各角色新菜单增量表
- §16.X v0.6.0 新增字段 / 新表汇总 + 11 端点列表
- §20.4 法务转化页双路径说明
- §22.8(本节)+ §22.9(话术 AI 算法)+ §22.10(培训案例自动入库)

**关键决策记录**
- **路径互斥防双轨**:督导直接移交端点校验本案件无 pending 申请(409 ERR_PENDING_REQUEST_EXISTS),不允许两条路径同时跑同一案件
- **风险事件处理结果复用 disposition 字段**:不新建 handled_at / handled_by 字段(Sprint 9.4 已有 disposition_note / disposition_by / disposition_at),只加 handle_status 状态机
- **培训库自动入库幂等**:`raw_risk_event_id` 唯一性 + `from_risk_event()` 已存在 case 直接返回(防 PATCH 重试时重复建)
- **PM 提醒不下沉为通知**:运营提醒是「实时计算的状态指标」(类似 dashboard 数字),没有读 / 未读语义;站内信是另一条事件流(详 §16 Notification)

---

### 22.9 话术 AI 评分算法(v0.6.0)

**公式**:`ai_score = recovery_rate × 70 + adoption_rate × 30`(clip 到 [0, 100])

**样本窗**:近 30 天(`lookback_days = 30`,可参数化)

**分子分母定义**:
- `total_shown = COUNT(SuggestionFeedback WHERE script_template_id=X AND created_at >= now - 30d)`
- `total_adopted = COUNT(... AND action='adopt')` — 催收员实际采用的次数
- `total_adopted_paid = COUNT(... AND action='adopt' AND case.stage='paid')` — 采用且案件已回款的次数
- `adoption_rate = total_adopted / total_shown`
- `recovery_rate = total_adopted_paid / total_adopted`

**为何 70/30**:PRD §20.1 核心 KPI 是回款,采用率是过程指标。回款率为终极指标加 70% 权重;采用率作为「催收员认可度」加 30%。后续可在本节调权重(单点修改 `app/services/script_ai_score.py:WEIGHT_RECOVERY / WEIGHT_ADOPTION`)。

**样本量保护**:
- `total_shown < 5`:不算分(`ai_score = NULL`),避免小样本误导
- `5-9`:正常算分,但 UI 显示「样本不足」⚠ 徽章(`ai_score_sample_count` 字段驱动)
- `>= 10`:正常展示

**调度**:
- 后端 `app/services/script_ai_score.py:recompute_ai_scores_loop()` — FastAPI lifespan 启动的 asyncio 循环
- 每 6h(`RECOMPUTE_INTERVAL_SEC`)检查一次「`ScriptTemplate.ai_score_updated_at` 最旧值 > 24h 前」,触发全量重算
- 手动触发:`POST /admin/scripts/recompute-ai-scores`(物业 admin,本租户范围)

**前端展示**:
- `admin/scripts/effectiveness.tsx` — 综合评分(0.6×采用率 + 0.4×好评率)+ AI 评分**并列**展示,加 tooltip 解释算法
- `supervisor/script-labels.tsx` — 表格加 AI 评分列(颜色分级:≥70 绿 / 40-70 橙 / <40 红);样本不足时灰显「样本不足(N)」

### 22.10 培训案例自动入库链路(v0.6.0)

**两条入库路径**(`app/services/training_curate.py`):

1. **风险事件 → 培训(联动)**
   - 督导在 supervisor/risk-events EventDetailModal 选 status=`transferred_training`
   - PATCH `/supervisor/risk-events/{id}` 调 `from_risk_event(db, risk_event_id, tenant_id, actor_user_id)`
   - 幂等:若同一 `raw_risk_event_id` 已有 training_case 直接返回
   - 自动文案:title="风险事件复盘:{trigger_text[:40]}";scenario 拼 level + category + trigger_text;lesson 取 disposition_note;category='escalate';rating=3 默认

2. **督导手工录入**
   - POST `/supervisor/training-cases` body={title, category, scenario, lesson, raw_call_id, rating}
   - source='manual',created_by=当前督导

**兜底循环** `scan_auto_ingest_loop()` — 每 24h 扫近 7 天「`handle_status='transferred_training'` 但 raw_risk_event_id 未建训练案」的事件,自动补建,防 PATCH 时联动失败。

**前端 training 页**:
- `useCustom` 拉真实 `/supervisor/training-cases`(mock fallback 当后端 0 条)
- 「自动入库」徽章(card 上 Sparkles 图标 + 蓝色)区分 source=auto vs manual
- category(4 类)+ source(auto/manual/all)双维度过滤
- 点「听原通话录音」+1 view 计数(POST `/{id}/view`,轻量端点不写 audit)

---

### 22.11 v0.7.0 服务商侧 5 角色与物业全面对齐(2026-05-21)

**背景**:人工测试反馈服务商管理员 7 个具体 UX 问题(优先级显数字 / 分配显 user_id / 「租户」文案 / 案件列表与看板对齐 / 团队 UI / 话术库参考物业 / App 培训等),并提出总方针:「物业管理员/督导/催收员/项目经理/法务对应的服务商 5 角色应功能、UI 对齐;唯一差异是数据权限 + 物业 admin 才能创建项目/导入案件」。Phase 1 调研发现服务商 nav 已 80% 对齐(12 项 vs 物业 admin 12 项),主要差距是 UI 细节 + 缺功能(话术 effectiveness / 项目详情页 / App 培训),**不是结构性差异**。

**6 Wave 拆分**:

| Wave | commit | 核心动作 |
|---|---|---|
| A 公共对齐基础 | `53f4c99` | 「合作租户→合作物业」13 处文案 + 抽离 `PriorityBadge` 共享组件 + 服务商案件 `assigned_to_name` 后端 JOIN + 团队 modal 改 RightDrawer + OTP 首登 |
| B 服务商 admin 5 大缺口 | `c7e48d2` | 「我的项目」独立详情页(后端 2 端点 + 整页只读 detail + KPI 3 卡)/ 案件列表+看板按项目过滤 + 项目列 / 话术 effectiveness 看板(后端 + 前端新页)/ dashboard 加 PmAlertsSection(抽离共享)/ 项目列表服务期 badge |
| C 督导 + 法务对齐 | `d1f0f51` | 服务商督导 nav 9→15 项全对齐(补案件管理 5 项 + 培训案例库)+ `supervisor_escalated` / `supervisor_actions` 9 端点加 scope 守卫(填 P0 安全缺口)+ 服务商法务无需改(职责本就窄,结论记录) |
| D 催收员 + PM 补全 | `fe74c87` | 物业 admin 案件看板加 PriorityBadge(对齐服务商)+ AuthUser 扩 work_mode/provider_id 字段 + agent 工作台显「服务商/物业内部」work_mode 徽章 + PM Top 5 点击跳详情 |
| E 催收员培训案例库 | `e56fe20` | 后端 2 agent 端点(GET 列表 + POST view +1)+ 前端 `/agent/training` 整页(只读浏览 + 4 类 filter + 详情 modal)+ nav 入口;App WebView 可访问 |
| F PRD 文档同步 | (本提交) | §3.5.1 服务商可见性边界 + §4.1.1 5 角色对齐表 + §18.0 话术三层归属 + §22.11 本节 |

**关键决策**:

1. **统一文案 vs 不动 path**:
   - 用户可见层:「租户」→「物业」(对齐用户心智)
   - 内部标识符:path / type / role 字段名不动(保持稳定 + 不破坏 grep / 现有引用)
   - OPS_NAV「租户管理」保留(平台 OPS 视角 vs 外部「物业」区分)

2. **PriorityBadge 抽离共享组件**:
   - 原物业 admin pool 有 inline `priorityBadge` helper,服务商侧 cases/index.tsx 裸数字「1800」用户看了懵
   - 抽到 `components/ui/PriorityBadge.tsx`,4 处(admin pool / admin kanban / provider cases / provider kanban)共用
   - 算法:`amount × 0.4 + months × 0.3` → 阈值分级(≥80 红 / 60-80 橙 / 40-60 蓝 / <40 灰)

3. **服务商团队改 OTP 首登**(对齐 admin/users):
   - 原 modal 写死默认密码 `Demo@123!` — 用户反馈 UI 有问题
   - 改 RightDrawer + 移除密码字段;后端 `password` 可选,缺省生成随机密码(后续走 OTP 短信邀请)
   - 跟物业 admin/users/new 体验完全一致

4. **服务商可见性 = `project.provider_id == self_provider_id`**(不走 Contract):
   - 这是 v0.7.0 调研确认的现状,**已锁定**(详 §3.5.1)
   - `ProviderTenantContract` 管签约关系(谁和谁签了 / 服务期 / 结算周期);**Project.provider_id 管「这个项目外包给哪个服务商」**
   - 复用 `_supervisor_scope.py` 三函数(`supervisor_case_filter` / `supervisor_call_filter` / `supervisor_agent_filter`)在 11+ 端点

5. **App 培训库走 WebView**(非 native Compose):
   - Android App 主屏是 4 tab WebView(home/cases/call-history/profile),非纯 Compose
   - 加 native Compose Screen 要新 Activity + 嵌套 navigation + 学习成本高
   - **改做 React 页面 `/agent/training` + nav 入口**;App WebView 自动可访问,跨平台一致
   - 后续如需 native 体验:Retrofit + Moshi DTO 已就绪,可在 `poc/android/screens/training/` 新增 List/Detail Screen + nested nav(`screens/dial/` `screens/realtime/` 等已有模板)

**P0 安全修复**(本期):
- 服务商督导可访问 `/supervisor/escalated` / `/supervisor/cases/*` 等端点时,原仅 `tenant_id` 过滤 → **服务商督导可越权看到该物业内非自家服务商接的案件**。Wave C 在 9 端点加 `supervisor_case_filter`,严格限定服务商督导只看本服务商接的项目。

**人工验收点**(全 push 完):
- 服务商 admin(13000000010):看「合作物业」+ 优先级 badge + 真实催收员姓名 + 「我的项目」详情页 + 团队 OTP 风格 + 话术效果页
- 服务商督导(13000000011):看 15 项 nav + 跨多物业接案的升级/承诺/超期管理(scope 守卫)
- 服务商催收员(work_mode=external):工作台看「服务商」徽章 + 培训案例库可浏览
- 服务商 PM:dashboard 看「合作物业 Top 5」(原「租户」)+ Top 5 跳详情

---

### 22.12 v0.8.0 诉讼证据中心(2026-05-21)

**背景**:产品讨论聚焦「区块链存证在前端如何体现 / 给哪些角色显示 / 内容是什么」。Phase 0 调研发现 `submit_attestation()` 当前**只在 `evidence_bundle.py` 一处被调用**(法务点「下载存证包」时)— 现有「按需上链」策略其实合理,只是 UI 没体现「证据状态」+ 缺「为何要上链」的法律语境提示。

用户(2026-05-21)进一步收敛三个边界:
1. 核心是**诉讼证据问题**,不是「记录催收过程」
2. 受众**只给物业法务 + 物业管理员**(不打扰催收员/督导/业主)
3. 法律上须区分「本地哈希(弱证据)vs 第三方存证(强证据)」

**4 Wave 拆分**:

| Wave | commit | 核心动作 |
|---|---|---|
| A 后端基础 | `b646592` | `mark_pending_attestation()`(L2 风险事件零成本标记)+ `attest_case_only()`(打包上链幂等)+ `GET /legal/cases/{id}/evidence-status` 聚合 + `GET /admin/blockchain/risk-overview` 风险敞口 + `GET /public/verify/{tx_hash}` 扩展 `ebaoquan_verify_url`(借易保全公信力)+ `supervisor_extras.py` PATCH 加 L2 自动 hook |
| B 法务证据中心 | `af1ac20` | `EvidenceStatusPanel.tsx` 共享组件(4 类细分对比表 + 弱/强法律效力提示 + 「打包上链 ¥99」/「下载证据包」/「生成证据清单」3 按钮)+ `/legal/cases/[id]` 集成 + `GET /legal/cases/{id}/evidence-receipt` HTML 证据清单端点(封面 + 通话表 + 风险事件表 + 核验说明引最高法 2018 第 11 号文,浏览器「打印为 PDF」) |
| C 物业 admin 视图 | `5ef00f6` | `EvidenceStatusBadge.tsx` 共享组件(三态外观 + CTA 智能分支)+ 集成到 `/admin/cases/[id]` 右栏 + `GET /admin/cases/{id}/evidence-status` admin 摘要端点 + `/admin/billing/blockchain` 升级双 tab(`BillingTab` 抽出 + `RiskExposureTab` 新建,3 KPI + 双色进度条 + Top 10 高风险表 + 「为什么要上链」帮助框)+ 菜单 「存证消费」→「存证管理」 |
| D PRD 文档同步 | (本提交) | §20.3.5 法律效力分级 + 触发策略 + §22.12 本节 |

**5 个关键决策**

1. **L2 风险事件「先标记、不立即上链」(策略 1c)** — 候选 1a 是「立即调易保全 ¥5/单」(开销大且 99% 案件不进诉讼);1b 是「完全不存证」(法务打包时手工补);1c 是「写 BlockchainAttestation 行但 status='pending' / tx_hash=NULL / cost=NULL,法务打包时一并捞出」。选 1c 因:零成本 + 同等法律效力(司法链关心 hash 上链时刻而非数据生成时刻)+ 自动幂等(预占位避免重复扫描)。

2. **受众收窄到法务 + 物业管理员** — 候选 2a 是全员看「区块链存证」徽章(用户决策前的方案);2b 是「只让法务看」(过度收窄,admin 无法判断风险敞口);2c 是「法务 + admin/PM/supervisor 三档可见性」(选定)。催收员/业主不暴露 — 避免「催收人员把上链当威胁话术」和「业主因恐慌支付,引发投诉」。

3. **物业 admin 不直接触发上链** — 候选 3a 是「admin 案件详情加「上链」按钮」(权责越界);3b 是「admin 只看不动,转法务时勾「同时上链 ¥99」」(选定 — UI 已在 ConvertToLegalModal 落地;真正触发权归法务)。

4. **公开核验 借易保全公信力(策略 C2)** — 候选 C1 是「自建核验页 + tx_hash 校验」(无第三方背书,对方律师质疑「平台自证」);C2 是「`/public/verify/{tx_hash}` 返回元数据 + 拼易保全官方核验 URL」(选定 — 律师/法庭在易保全官网查更可信)。

5. **证据清单选 HTML 而非 PDF** — 候选 P1 是 `reportlab` 生成 PDF(+ 5MB 依赖 + 中文字体配置);P2 是 `weasyprint`(+ Cairo/Pango 系统依赖);P3 是纯 HTML 让浏览器「打印为 PDF」(选定 — 零新依赖 + 法律效力一致 + 法务在浏览器「另存为 PDF」一步到位)。

**P0 缺口修复**(本期):
- `BlockchainAttestation.status='pending'` 枚举此前**从未使用** — 现激活,L2 处置时由 `services/blockchain.py:mark_pending_attestation()` 写入
- `public/verify` 返回的 `block_height` 字段此前 `int` 强类型 — 改 `int | None` 支持 pending/failed 行
- L2 处置 PATCH 端点(`supervisor_extras.py`)此前不留存证痕迹 — 现自动 hook 写 pending 行 + 幂等检查(同 risk_event_id 已存在则跳过)

**人工验收点**(全 push 完):
- 物业法务(13000000006):案件详情看「证据状态」面板 → 点「打包上链 ¥99」→ 状态变绿 → 点「生成证据清单」浏览器开 HTML → 打印为 PDF
- 物业管理员(13000000002):案件详情看右栏「证据状态」徽章(灰/黄/绿三态)→ 菜单「存证管理」切「风险敞口」tab → 看 Top 10 + 「查看案件 →」
- 公开核验(无需登录):浏览器开 `/api/v1/public/verify/{真实 tx_hash}` → 返回元数据 + 易保全核验跳转链接

---

## 23. UI 模式与术语约定(v0.5.6 起)

### 23.1 弹窗交互模式

详见 [`docs/UI_PATTERNS_MODAL.md`](./UI_PATTERNS_MODAL.md)(SSOT)。要点:

| 内容类型 | 推荐 | 实现 |
|---|---|---|
| 简单确认(是/否、驳回理由) | 中间 Dialog ≤ 420px | `.modal-overlay` + `.ds-modal` |
| 表单 ≤ 3 字段 | 中间 Dialog ≤ 520px | 同上 |
| 表单 ≥ 4 字段 / 需边看列表上下文 | **右侧 Drawer 可拖动宽度** | `RightDrawer`(基于 @radix-ui/react-dialog) |
| 大量信息展示 | 右侧 Drawer ≥ 700px / 全屏页 | 同上 |
| 移动端 | BottomSheet | App-only |

样板:`SupervisorReassignModal`(督导重新分配)v0.5.6 已迁移到 RightDrawer;其他 14 modal 按业务优先级渐进改。

### 23.2 角色文案术语

**SSOT**:`frontend/src/lib/roleLabel.ts`。

- 物业租户内:`admin` → **「物业管理员」**(对外文案);`supervisor` → 督导;`agent` → 催收员;`legal` → 法务对接人;`coordinator` → 运营协调;`project_manager` → 项目负责人
- 服务商:`admin` → **「服务商管理员」**;`agent` → 服务商催收员;其余同上
- 平台:`superadmin` → 平台超管;`ops` → 平台运营

**禁止**:用户可见文案里直接写「admin」「Admin」「admin 视角」「转 admin」等英文+中文混排。

代码逻辑里 `role === "admin"` 字段标识符**不受影响**。

### 23.3 AI 视觉巡检 / a11y(可选)

`docs/QA_PLAYBOOKS/vision-audit.md` 落地了一套手动跑的 UX 巡检流程:Playwright 截图 → Claude Vision 分析 → Markdown 报告。同时 `e2e/a11y-audit.spec.ts` 用 axe-core 跑 WCAG 2.1 A+AA 扫描。两者均**不进 CI**,定位「发版冒烟 checklist 的手动步骤」。

---

*下一步：UI 设计 → 全栈开发*
