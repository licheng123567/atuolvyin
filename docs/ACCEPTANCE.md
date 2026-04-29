# 验收标准（ACCEPTANCE）

> 引用 `docs/DESIGN_SPEC.md` §6 性能基线和交付 checklist，本文档不重复，只扩展。

---

## 1. 通用完成定义（DoD）

任何功能进入"已完成"状态，必须同时满足：

| 维度 | 标准 |
|------|------|
| 功能 | PRD §21 对应页面的核心操作全部可用，无 501 Not Implemented |
| 测试 | 单元测试覆盖率达标（见 TESTING_STANDARDS.md §3）；关键路径 E2E 测试通过 |
| 视觉 | 与 HTML 原型（`ui/*.html`）一致；响应式在 1280px / 1440px / 1920px 下正常 |
| 可访问性 | 表单有 label；错误状态有文字说明；键盘可操作主要动作 |
| 性能 | 列表首屏 ≤ 1.5s（LCP）；API 响应 P90 ≤ 300ms（见 DESIGN_SPEC §6.2）|
| 安全 | 手机号脱敏；多租户隔离验证（跨租户请求返回 404/403）|

---

## 2. Sprint 0：认证 & Layout Shell 验收

### 登录 / 会话管理（auth）

| 验收项 | 条件 |
|--------|------|
| 登录成功 | 正确手机号+密码 → 返回 `access_token`；前端存 localStorage；跳转首页 |
| 登录失败 | 错误密码 → 401 `ERR_INVALID_CREDENTIALS`；前端显示错误提示 |
| 未激活账户 | `is_active=false` → 401 `ERR_USER_INACTIVE` |
| 受保护路由 | 未携带 token 访问任意受保护页面 → 重定向 `/login` |
| 登出 | 调用 `authProvider.logout()` → 清除 localStorage → 重定向 `/login` |
| token 写入 | JWT payload 含 `user_id / tenant_id / role / scope / exp`（HS256, 24h）|
| CORS | `localhost:5173` 可发跨域请求；生产域名在 `ALLOWED_ORIGINS` 环境变量配置 |

"Auth 完成"定义：上述 7 项全部通过；`tests/api/test_auth.py` 5 个集成测试绿色。

### Layout Shell（sidebar / topbar / AppLayout）

| 验收项 | 条件 |
|--------|------|
| Sidebar 宽度 | 240px（`var(--sidebar-width)`），含 Logo 区 + 导航区 + 用户信息区 |
| Topbar 高度 | 56px（`var(--topbar-height)`），含页面标题插槽 |
| 布局结构 | `AppLayout` 渲染 sidebar（左） + 主内容区（右），主内容区可独立滚动 |
| 路由保护 | 所有 `<AppLayout>` 内路由被 `<Authenticated>` 包裹；无 token 时跳转登录 |
| 视觉一致 | 颜色使用 CSS 变量（`var(--color-primary)`），无硬编码 HEX |

---

## 3. P0 页面验收一览

> 状态来自 `docs/UI_GAPS.md`（✅ UI 已完成 / ⚠️ 部分缺失 / ❌ 未实现）
> 每个页面的"完成条件"对应后端接口 + 前端页面双双落地。

### 角色 4：物业公司管理员（admin）

| 页面 | 核心验收条件 |
|------|------------|
| 管理看板（a-dashboard）| 今日外呼/接通/承诺缴费/实际回款 4 个指标实时更新；分钟用量/配额可见 |
| 案件列表（a-cases）| 支持状态/催收员/金额段筛选；分页；导出 Excel |
| 案件详情（a-case-detail）| 业主信息完整；活动时间线展示通话历史；工单/法务关联可点击 |
| 公海管理（a-pool）| 公海案件列表；批量分配给催收员；分配后从公海消失 |
| 名单导入（a-import）| Excel 上传；字段映射；重复检测；导入结果摘要 |
| 用户管理（a-users）| 创建内部员工；邀请外部兼职（生成链接）；停用恢复；批量导入 |
| 项目管理（a-projects）| 创建项目；指派物业侧负责人；项目状态可见 |

### 角色 5：主管/督导（supervisor）

| 页面 | 核心验收条件 |
|------|------------|
| 工作台（sv-workspace）| 实时通话状态看板；团队今日统计；分钟用量趋势 |
| 案件分配（sv-cases）| 批量分配；重新分配；优先级调整 |
| 通话复核（sv-review）| 抽查录音 + 转写；标注质量；AI 判断 vs 人工判断对比 |
| 升级案件处理（sv-escalated）| 升级案件列表；处理动作（转工单/转法务/关闭）|
| 团队绩效（sv-performance）| 接通率/承诺率/回款率排名 |

### 角色 6B：内部催收员（PC）

| 页面 | 核心验收条件 |
|------|------------|
| 通话工作台（my-workspace）| 三栏布局；AI 话术卡实时推送；风控干预可见；通话控制 |
| 我的案件（my-cases）| 私海列表；筛选；详情侧滑（案件信息 + 欠费明细 + 时间线）|
| 个人绩效（my-stats）| 本月通话/承诺/回款；本月通话分钟数 |

### 关键路径端到端验收

| 流程 | 验收条件 |
|------|---------|
| 欠费导入→分案→拨打→ASR→AI提示 | 全链路在测试环境一次跑通；录音上传成功；转写有内容；AI 推送出现 |
| 分钟配额超限拦截 | 将租户配额设为 1 分钟，发起第二个通话时返回 403 Quota Exceeded |
| 多租户隔离 | 用租户 A 的 token 请求租户 B 的案件返回 404 |
| 手机号脱敏 | API 响应的 phone 字段格式为 `138****1234`；数据库存储为密文 |

---

## 3. 不在验收范围的项（P1，v1.1）

- 服务商合作管理（a-partners）
- 数据报表（a-reports）
- 合规月报（a-compliance）
- 区块链存证集成
- 在线支付
- 撮合市场
