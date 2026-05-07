# v1.6 — UI 还原 + 死端点清理 + 工单优先级建模

发布日期：2026-05-06
基线：v1.5.0-rc1（`d1482e8`）→ HEAD（`acb29b7`）= 8 个 commit

## 概要

v1.6 是 **polish + cleanup** 性质 sprint，无新增业务模块。三条主线：

1. **UI 还原 5 项**：把 React 实现与 `ui/*.html` 设计稿对齐
2. **死端点清理**：用户决策保留"直接创建用户带密码"路线后，删除 invite stub
3. **工单优先级建模**：补齐 PRD §10.4 设计稿（4 档 badge）但 React 端缺数据字段的建模缺口

## 详细变更

### A. UI 还原（B 路线收尾）

| commit | 变更 |
|---|---|
| `fb181b0` | login 双面板设计：左 480px 暗色品牌渐变 + 4 大特性卡片（Headphones/TrendingUp/Scale/Smartphone）+ 右表单（Eye/EyeOff 密码切换 + sessionStorage 多设备踢出横幅） |
| `92a4a1e` | cases kanban 6 列头改语义化背景（待联系灰/跟进中蓝/承诺缴费橙/已缴费绿+✓/升级中紫/已关闭灰）+ 卡片金额改红色 14px bold；Topbar 增租户名 + 11 角色色系 badge（auth/login response 同步加 `tenant_name` 字段） |
| `04773a3` | legal `enforcing` 阶段 badge 紫色（badge-purple "强制执行申请中"）；RealtimeCallShell 列宽 240/1fr/340 对齐 ui/agent-pc.html 4 栏 |

随附 `docs/UI_RESTORATION_STATUS.md` 盘点：14 个 v1.4/v1.5 反向出的原型「天然对齐」无需重做；5 个 v1.0 时期 HTML 标记 v1.6 候选（已全部完成）。

### B. 死端点清理（commit `ebc87df`）

`/api/v1/admin/users/invite` 删除：
- 原 stub 返回 token 但**从不持久化**（注释承认 Sprint 2 deferred），且 url 指向不存在的 `/register` 页 = 完整路径无法走通的死代码
- 删除范围：endpoint + InviteLinkRequest/Response schema + 1 项测试 + 模块 import
- `docs/FRONTEND_BACKEND_ALIGNMENT_AUDIT.md` 评估结论同步：FE↔BE 对齐 100%；suggestion-config 保留（ws/call_session.py 活跃读取）

### C. suggestion-config UI 集成（commit `d5b6548`）

把原本只能通过 API 调用的 `/admin/suggestion-config` 接入 admin/settings：
- 独立卡片「AI 话术推送」展示 sensitivity (1-5) + max_per_push (1-10)
- 顺手修原 `setForm`-in-effect 反模式：用 `useRef` tracking init 标志而非 state guard，规避 react-hooks/set-state-in-effect lint 错误

### D. 工单优先级 4 档建模（commit `acb29b7`）

PRD §10.4 工单原型（ui/workorder.html）展示了 priority 4 档 badge，但 React 端建模缺口。本次补齐：

**数据层**：
- alembic `20001v16`：`work_order` 增 `priority VARCHAR(16) NOT NULL DEFAULT 'normal'`
- CHECK 约束：`priority IN ('urgent_critical', 'urgent', 'normal', 'low')`
- ORM + WorkOrderCreate/Patch/Out + list endpoint `?priority=...` 过滤参数

**前端**：
- `helpers.ts` 增 `WORK_ORDER_PRIORITIES` + `formatPriority` + `getPriorityColor`
- 列表表格新增「优先级」列 + 顶部 priority 过滤 select
- 新建页表单加 priority select（默认 normal）
- 详情页 header 多挂 priority badge + 表单加 priority 编辑器

**配色**（对齐 ui/workorder.html badge 风格）：

| code | 标签 | 色系 |
|---|---|---|
| `urgent_critical` | 很紧急 | 红（var(--color-danger-light/danger)） |
| `urgent` | 紧急 | 橙（var(--color-warning-light/warning)） |
| `normal` | 一般 | 灰（var(--color-neutral-100/600)） |
| `low` | 低 | 灰 |

**PRD §10.4** 同步追加 v1.6 优先级表（含 code / 标签 / 配色 / 触发场景）。

### E. 法务工作台动作按钮补齐（commit `ef4d325` — v1.5.x 末尾 patch）

dispatch / complete / cancel 三个动作按钮（pending/dispatched/in_service 状态机分别可见）；`docs/FRONTEND_BACKEND_ALIGNMENT_AUDIT.md` 首版同步落地。

## 测试

| 套件 | v1.5 基线 | v1.6 末态 | 增减 |
|---|---|---|---|
| backend pytest | 524 | 527 | +4 work_order priority -1 invite |
| frontend vitest | 150 | 150 | 0 |
| alembic round-trip | 18002v14 → 19001-19004v15 链 | + 20001v16 链 | 自动覆盖 |

后端首次跑通 `tests/test_alembic_roundtrip.py` 自动验证 v1.6 migration 升降级干净。

## 已知约束

- v1.0 时期 `platform-superadmin.html` 12 个 sub-section 设计稿，React 仅实现核心 4 页（health/audit/cost/plans），其余明确推 v2.x 候选
- `suggestion-config` 已挂 admin/settings UI 入口；其余配置（recording_mode auto 决策树阈值等）仍只能通过 API 改

## 迁移命令（升级现网）

```bash
# 后端
cd poc/backend
alembic upgrade head   # 19004v15 → 20001v16

# 前端
cd frontend
npm install            # 无新增依赖；如有 lockfile drift 走一次
npm run build
```

## 回滚策略

```bash
alembic downgrade 19004v15  # 撤回 work_order.priority 字段 + CHECK 约束
```

users/invite 端点删除是不可回滚的代码删除（schema 也删了）；如真需恢复，回滚 commit `ebc87df` 即可。
