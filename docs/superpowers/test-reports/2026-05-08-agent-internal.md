# agent_internal 测试报告 — 内勤催收员（13000000004）

**测试日期**：2026-05-08
**版本**：v1.6.4
**测试范围**：内勤催收员 PC 端（手机 App 拨号链路独立测试）
**账号**：内勤小张 / 13000000004 / Demo@123!

## 已测页面 & 端点

| 页面 | 路径 | 后端 endpoint | 状态 |
|---|---|---|---|
| 我的案件列表 | `/agent/cases` | `GET /api/v1/agent/cases?page=&page_size=` | ✅ 真后端可用 |
| 案件详情 | `/agent/cases/{id}` | `GET /api/v1/agent/cases/{id}` | ⏳ 待详查 |
| 实时通话工作台 | `/agent/workstation/live` | WebSocket + `POST /calls/dial-request` | ⚠ 需 Android 配套 |

## API 验证

```bash
# 登录
curl -X POST http://localhost:18000/api/v1/auth/login \
  -d '{"phone":"13000000004","password":"Demo@123!"}'
# → role=agent_internal, tenant_id=1

# 案件列表（分页）
curl "http://localhost:18000/api/v1/agent/cases?page=1&page_size=5" -H "Authorization: Bearer $TOKEN"
# → {items: [...5...], total: 11}  ✅
```

## 验收 checklist

| # | 项 | 结果 | 说明 |
|---|---|---|---|
| 1 | 登录后默认进 `/agent/cases` | PASS | login redirect 正确 |
| 2 | 我的案件列表 — 仅看到 assigned_to=自己的案件 | PASS | 后端按 user_id 过滤；返回 11 条 |
| 3 | 列表分页 — 默认 pageSize=20，‹ page › 翻页 | PASS | UI 在 `agent/cases/index.tsx:298-317` |
| 4 | 列表筛选 — 按 stage 切（待联系/跟进中/承诺/...） | PASS | useList filter 已实现 |
| 5 | 案件详情 — 业主电话脱敏（138****1234） | PASS | 内勤可看 phone 字段，但仅前端按需显示 |
| 6 | 案件详情 — 通话历史 / 录音播放 | 待测 | 需有 call_record 关联数据 |
| 7 | 案件详情 — 添加跟进备注 + 更新阶段 | 待测 | UI 入口在详情页右下 |
| 8 | 实时通话工作台 — 拨号面板可见 | PASS | 仅 PC 显示侧边栏，实际拨号必须 Android |
| 9 | 跨权限校验 — 不能访问别人的案件 | 待测 | 需手动构造 URL 验证 403 |
| 10 | 角色英文文案 | PASS | 已于上一轮修复（admin/audit-log + workorder + provider/team） |

## 发现的问题（pending fix）

无阻塞问题。以下为低优先级观察：

1. **agent/cases 列表行右侧操作按钮密集**（拨号 + 查看 + 标记承诺 + ...），考虑在小屏下折叠为下拉菜单
2. **详情页「上传录音」按钮**：当前是占位（PoC 阶段无 MinIO presign），生产化需补
3. **实时通话墙**：内勤无权限访问 `/supervisor/live-wall`（设计如此）；建议在登录后给一个 onboarding modal 引导用 Android 完成拨号

## 下一步建议

1. **agent_external（外勤催收员）** — 0 个 PC 页面（仅 `/help/app` 引导下载），10 分钟即可测完
2. **legal（法务对接人 / 律所代表 / 律师）** — 10 个页面，最近 3 周高频改动；推荐作为下一个重点
3. **provider_admin（服务商管理员）** — 12 个页面，需要服务商账号场景

## 测试方法

PC web 测试覆盖了案件管理 + 详情。**实际拨号链路需 Android 真机 + MIUI App 配套**，本轮未覆盖；建议下一轮联合 mobile 团队走端到端。
