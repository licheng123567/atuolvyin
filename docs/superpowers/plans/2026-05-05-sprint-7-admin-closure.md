# Sprint 7 — admin 闭环（看板 + 公海 + 案件看板 + 详情补齐）

> 批 2A 第 1 个 sprint。让物业管理员能从登入到处理案件全流程跑通。

**Goal**：补齐 admin 角色 4 个 P0 页面 + 必需的后端 dashboard API。

**Architecture**：纯前端补页 + 1 个后端 stats endpoint。沿用现有 schema、Refine hooks、现有路由结构。

**Tech Stack**：FastAPI（1 个新 endpoint）+ React + Refine + lucide-react。

---

## 后端

### Task 1：admin dashboard stats endpoint

**Files**:
- Create: `poc/backend/app/api/admin_dashboard.py`
- Create: `poc/backend/app/schemas/dashboard.py`
- Modify: `poc/backend/app/main.py`（注册 router）
- Create: `poc/backend/tests/api/test_admin_dashboard.py`

**Endpoint**: `GET /api/v1/admin/dashboard/stats`

**Response shape**（Pydantic）:
```python
class AdminDashboardStats(BaseModel):
    today: TodayStats        # outbound_count, connected_count, promised_count, recovered_amount
    minute_quota: QuotaStats # used_min, total_min, remaining_min, warning (used >= 80%)
    public_pool_count: int
    risk_alert_count_7d: int
    top_agents: list[AgentRanking]      # 全员排名 top 10（today/month 切换）
    script_adoption_trend: list[float]  # 近 7 天采用率
```

**实现要点**：
- 多租户：用 `tenant_id` 过滤所有查询
- 仅 `role=admin` 角色可访问（require_roles）
- 性能：单次查询尽量复用 SQL（避免 N+1）；如果要起多个 query 用 `asyncio.gather` 也可以，但本 endpoint 是 sync
- script_adoption_trend：从 `suggestion_feedback` 表 group by date 计算 adopt/total
- risk_alert_count_7d：从 `risk_event` 表（5a 加的）count 近 7 天 supervisor_alert_emitted=True

**Steps**:
- [ ] 写测试 `test_admin_dashboard.py`：`test_admin_can_get_stats`、`test_non_admin_forbidden`、`test_returns_empty_when_no_data`
- [ ] 红：`pytest tests/api/test_admin_dashboard.py -v`
- [ ] 实现 schema + router + main.py 注册
- [ ] 绿：`pytest tests/api/test_admin_dashboard.py -v`
- [ ] 全量回归：`pytest tests/`
- [ ] Commit: `feat(5b-T7-1): admin dashboard stats endpoint`

> 注：sprint 编号用 5b-T7-N 是历史延续；本 sprint 实质是 sprint 7。

---

## 前端

### Task 2：admin 管理看板首页

**Files**:
- Create: `frontend/src/pages/admin/dashboard/index.tsx`
- Modify: `frontend/src/App.tsx`（加路由 + 改 ROLE_HOME 把 admin 指向 `/admin/dashboard`）
- Modify: `frontend/src/config/nav.ts`（admin 菜单加"控制台"项 → `/admin/dashboard`）

**UI 参考**：`ui/admin.html` `#a-dashboard`（5 个 KPI 卡 + 全员排名表 + 风控告警卡）

**Steps**:
- [ ] 写 helpers test（如有可测纯函数：`formatMinutes(n)`、`getQuotaColor(used, total)` 在用量>=80% 返橙色）
- [ ] 实现 5 KPI 卡（今日外呼/接通/承诺/回款/本月分钟用量+橙色警示）+ Top10 排名表 + 风控告警计数 + AI 话术采用率折线（用 recharts 或纯 SVG）
- [ ] 用 `useCustom` 调 `/admin/dashboard/stats`
- [ ] tsc + vitest 通过
- [ ] Commit: `feat(sprint7-T2): admin dashboard page`

### Task 3：admin 案件看板

**Files**:
- Create: `frontend/src/pages/admin/cases/kanban.tsx`
- Modify: `App.tsx`（路由）+ `nav.ts`（菜单"案件看板"）
- Modify: `frontend/src/pages/admin/cases/index.tsx`（顶部加"列表/看板"切换按钮）

**UI 参考**：`ui/admin.html` `#a-kanban`（6 列：待联系/跟进中/承诺缴费/已缴费/升级中/已关闭）

**实现**:
- 用 `useList` 一次拿全部案件（不分页，加 size=200 上限），前端按 `stage` 分组渲染 6 列
- 拖拽：`@dnd-kit/core` 或 HTML5 原生 dnd（先用原生避免新依赖）
- 拖拽后调 `useUpdate({ resource: 'admin/cases', id, values: { stage }})` —— 注意后端 endpoint 是 PATCH `/admin/cases/{id}/stage`，dataProvider 拼出来是 PATCH `/admin/cases/{id}`，需用 `useCustomMutation` 显式调 `/admin/cases/{id}/stage`
- 每列卡片显示：业主名 + 欠费金额 + 月数 + 当前 agent 名

**Steps**:
- [ ] 写 helpers test（如：`groupByStage(cases) -> Record<Stage, Case[]>`）
- [ ] 实现拖拽 + 调用后端 PATCH stage
- [ ] tsc + vitest
- [ ] Commit: `feat(sprint7-T3): admin case kanban view`

### Task 4：admin 案件详情补齐

**Files**:
- Modify: `frontend/src/pages/admin/cases/detail.tsx`

**当前缺失**（GAP_ANALYSIS）：
- 欠费明细分项展示
- 活动时间线（跟进备注、状态变更条目）—— 仅有 calls[] 转写
- 操作按钮：分配、转法务、建工单

**实现**:
- 欠费明细：从 case.amount_owed + months_overdue 计算月度物业费列表（mock 即可：amount/months 平均分到各月）
- 活动时间线：合并 calls + 状态变更日志（如有则从 case.activity_log 渲染；如后端无此字段，本任务先用 calls[] 倒序展示，标"v1.1 加跟进备注"）
- 操作按钮：
  - 分配：弹 modal 选 agent → POST /admin/cases/assign
  - 转法务：暂用占位 toast "v1.1 上线" （后端无 endpoint）
  - 建工单：暂用占位 toast "v1.1 上线"

**Steps**:
- [ ] tsc 通过
- [ ] Commit: `feat(sprint7-T4): admin case detail enrichment`

### Task 5：admin 公海管理

**Files**:
- Create: `frontend/src/pages/admin/pool/index.tsx`
- Modify: `App.tsx` + `nav.ts`

**UI 参考**：`ui/admin.html` `#a-pool`

**实现**:
- `useList({ resource: "admin/cases", filters: [{ field: "pool_type", value: "public" }, { field: "ordering", value: "-priority_score,-amount_owed" }] })`
- 表格：业主/欠费/月数/优先级/创建时间/操作（"分配"按钮）
- 右侧卡片："各员工私海数量"——用 `useList({ resource: "admin/users" })` + 每用户 `case_count` 字段（如后端无，本任务可用占位"加载中"或显示员工列表无 count）
- "释放规则状态"：占位"30 天未联系自动回公海"+ 静态说明

**Steps**:
- [ ] tsc 通过
- [ ] Commit: `feat(sprint7-T5): admin public pool management page`

---

## Verification

- [ ] 后端 188+1 测试通过，无回归
- [ ] tsc --noEmit 0 errors
- [ ] vitest 全过
- [ ] 浏览器手动：admin 登入 → 直接进 `/admin/dashboard` 看到 KPI 卡 → 切换案件看板 → 拖拽流转 → 进案件详情看活动时间线 → 进公海管理列表

## 收尾

- finishing-a-development-branch：push + PR + 合 main + 清 worktree（同 sprint 6 流程）
- 进 Sprint 8 = agent 实时通话工作台风控 UI 补全 + agent_external 脱敏守卫 + supervisor 质检复核工作台
