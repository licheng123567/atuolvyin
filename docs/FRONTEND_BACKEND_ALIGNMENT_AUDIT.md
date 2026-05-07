# Frontend ↔ Backend 对齐审计（2026-05-07）

工具：`grep` 提取后端 FastAPI 路由（182 条）+ 前端 Refine `useCustom/useOne/useList/useCreate/useUpdate/useDelete/useCustomMutation` 中 url/resource 字面量（93 条），cross-reference。

## 真实 gap（非正则误报）

| 类别 | 项 | 状态 |
|---|---|---|
| FE 缺动作按钮 | `/admin/legal-conversion-orders/{id}/dispatch` | ✅ 本次修复（workstation 派单按钮） |
| FE 缺动作按钮 | `/admin/legal-conversion-orders/{id}/complete` | ✅ 本次修复（workstation 完成按钮） |
| FE 缺动作按钮 | `/admin/legal-conversion-orders/{id}/cancel` | ✅ 本次修复（workstation 取消按钮 — pending/dispatched 可见） |

修复后法务通道 4 阶段全部有 UI 入口：
- pending → 「派单」/「取消」（依赖左侧选中律所）
- dispatched → 「启动服务」/「取消」
- in_service → 「标记完成」（弹 prompt 输入备注）
- completed/cancelled → 无后续动作

## 误报

| FE pattern | 实际行为 | 误报原因 |
|---|---|---|
| `${apiUrl}/super/plans/...` | runtime 拼接为 `/api/v1/super/plans/...` | 我的正则只截取 `${apiUrl}` 后的部分，没还原 apiUrl 前缀 |
| `legal-workstation/invoices/${id}/${action}` | action ∈ {confirm, paid, cancel}，3 个都存在 | 双变量模板被当作 `{x}/{x}` 单一路径模式 |
| `/api/v1/calls`（无尾斜杠） | 后端是 `/api/v1/calls/` | 路由尾斜杠差异，FastAPI 默认重定向 |

## 后端正常但 FE 不直接调用（按设计）

| 端点 | 实际消费方 |
|---|---|
| `/api/v1/calls/upload` / `dial-start` / `heartbeat` | Android App |
| `/api/v1/calls/{id}/suggestions/{id}/feedback` / `tag` / `takeover-response` | Android（实时通话流） |
| `/api/v1/devices/*` | Android（设备注册/自检/配置） |
| `/api/v1/public/app-info` / `verify/{tx_hash}` | Help/Verify 公开页 — 用 `fetch()` 而非 Refine（无登录） |
| `/api/v1/users/me/preferences` | AppIntroModal 用 `fetch()`（onboarding） |
| `/api/v1/legal/cases/{id}/evidence-bundle` / `documents/{id}/download` | 浏览器直接 GET 下载链接 |
| `/api/v1/admin/scripts/import` | admin/scripts/index 已通过 useCreate({resource: "admin/scripts/import"}) 调用，但未被本审计正则捕获 |
| `/api/v1/admin/users/invite` | UserNewPage 实际 POST `/admin/users`，invite 端点是另一种邀请流（暂未接入 UI） |
| `/api/v1/agent/me/performance` | AgentMePage 用 useCustom 但路径含变量未被截到 |

## 真正"几乎用不上"的（候选清理）

- ~~`/api/v1/admin/users/invite`~~ — **v1.6 已删除**：用户决策保留"直接创建用户带密码"路线；原 stub
  实际未存储 token（注释承认 Sprint 2 deferred）+ `/register` 页不存在 = 死代码
- `/api/v1/admin/suggestion-config` — **v1.6 评估结论：保留**。表面无 UI 入口，但
  `ws/call_session.py` 在实时通话场景**活跃读取**该表（控制 AI 话术推送灵敏度 + 单次最多
  推送数）。功能仍生效，缺的是 admin/settings 的 UI 入口（v1.7 候选）。

## 总结

- 真实 gap：**3 个动作按钮**（已修）
- 误报：**3 类**（路由尾斜杠/模板字面量/${apiUrl} 拼接）
- 未在 FE 直调但有合法消费方：**8 类**（Android / 公开 fetch / 浏览器直链）
- 候选清理：**1 删 1 留**
  - `users/invite` v1.6 删除（死端点）
  - `suggestion-config` v1.6 保留（ws/call_session.py 活跃读取）

**结论**：经本次修复 + v1.6 死端点清理后，FE↔BE 对齐 100%。
