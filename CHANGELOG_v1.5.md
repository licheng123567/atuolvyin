# 有证慧催 v1.5 — Release Notes

**发布日期**：2026-05-06（候选）
**Sprint 范围**：15.1 – 16.4 + UI 原型反向出 + 模板与文档完善
**累计提交**：30+ commits（v1.4 起算）
**测试覆盖**：pytest 524 项绿（含 +90 项新增 + 1 项 alembic round-trip）

## 一、v1.4 — 实时通话同步 / 引导下载 / 计费分离 / 安全基座（B 路线）

### Sprint 14.x（v1.3 实际推到 v1.4）
| 模块 | 内容 |
|---|---|
| 14.1 计费分离 | `tenant_minute_usage.realtime_minutes` / `post_minutes`；`call_record.recording_mode`；`plan_config.monthly_realtime_minutes` |
| 14.2 实时通话墙 | `POST /api/v1/calls/dial-start` + heartbeat + 90s 超时清理；`/supervisor/live-wall` 前端 + Android 接入 |
| 14.3 App 引导 | `user_account.preferences` JSONB；首次登录 modal + `/help/app` 公开页 |
| 14.4 PRD 落字 | §10.1 / §11.6 / §20.1.1 / §8.2 |

### Sprint 15.x — B 路线安全基座
| 模块 | 内容 |
|---|---|
| 15.1 多设备踢出 | `active_session` 表 + JWT `jti` 唯一化 + 登录 UPSERT + token hash 校验 |
| 15.2 L3 自动挂断 | risk-detector 检测到 L3 → `dispatch_force_hangup` WS 推送 + 审计 + 配额回滚 |
| 15.3 督导一键介入 | `dispatch_takeover_request` / `dispatch_takeover_response` WS 三方握手 + 审计 |
| 15.4 通知触发器 | `notification` 表 + 4 渠道 dispatcher（system/sms/wechat/dingtalk）+ 5 事件订阅（quota / script_disabled / wo_completed / case_escalated / promise_expiring）+ 前端 NotificationBell + drawer |

## 二、v1.5 — 法务转化通道（A 路线，PRD §20.4 实施层）

### Sprint 16.1 — 法务转化通道首切
- 新表 `legal_service_package`（4 个平台默认）+ `legal_conversion_order`
- 服务层：`recommend_package`（金额阶梯 + 置信度）、`build_timeline_summary`（聚合通话历史）、`estimate_cost`（含小额诉讼受理费 + 回款概率）
- 8 个 API 端点（preview / convert / list / detail / dispatch / complete / cancel）
- 状态机 `pending → dispatched → in_service → completed`（或 `cancelled`）
- 前端：`/admin/legal-conversion` 订单列表 + `ConvertToLegalModal`（preview→选包→下单）

### Sprint 16.2 — 律所池 + 法务工作台
- 新表 `law_firm` + `law_firm_lawyer`；扩 `legal_conversion_order` 加 `law_firm_id` / `lawyer_id` FK
- ops 端 CRUD（list / create / detail / patch / soft-delete + 嵌套 lawyers add/patch/remove）
- `dispatch` 升级：`law_firm_id` 优先（denormalize 名字快照），保留 free-text 回落；律师必须属该律所
- `complete` 时律所 `completed_orders` 自动 +1
- 新 module `/api/v1/legal-workstation/`：list orders + start service（dispatched→in_service）+ firm stats
- 前端：`/ops/law-firms` 管理页 + `/ops/legal-workstation` 工作台

### Sprint 16.3 — 法务订单结算流
- 新表 `legal_platform_invoice`（`unique(law_firm_id, period_start, period_end)` 防重复）
- 服务层：`aggregate_completed_orders` + `generate_invoice`（幂等）+ `total_unpaid_fee`
- API：generate / list / confirm / paid / cancel；`DRAFT → CONFIRMED → PAID` 状态机
- firm stats 增 `platform_fee_unpaid` 字段
- 前端：法务工作台增「介绍费账单」面板 + 「生成上月账单」+ 状态机操作按钮

### Sprint 16.4 — 法律文书自动生成
- 新表 `legal_document_template`（4 条平台默认 + 租户级覆盖）+ `legal_document_render`（多版本）
- 服务层：mustache `{{var}}` 替换 + `build_order_render_context` 聚合（租户/案件/业主/律所/律师/通话历史）
- API：list templates / get latest doc / render new version / list versions
- 前端：`LegalDocumentModal` preview / 复制 / 重新生成；订单列表新增「文书」列

## 三、UI 原型 1:1 反向（共 14 个 HTML 文件）

### P0 hero（5）
- `supervisor.html#sv-livewall` 实时通话墙
- `agent-workstation-live.html` / `admin-workstation-live.html` 实时通话工作台（坐席+督导旁听）
- `help-app.html` / `verify.html` 公开页

### P1（10 React 页 / 8 文件）
- `supervisor-review-detail.html` 督导复核详情
- `supervisor-risk-events.html` 风控事件时间线
- `admin-scripts-effectiveness.html` 话术效果看板（A/B/C/D 评级）
- `admin-scripts-versions.html` 话术版本历史
- `admin-compliance-detail.html` 合规月报详情（含打印样式）
- `admin-settlement-detail.html` 结算单详情
- `admin-provider-detail.html` 服务商详情
- `admin-user-new.html` / `workorder-new.html` / `admin-risk-keyword-form.html` 表单页

### P2（9 项 / 1 新文件 + 8 既有 anchor）
- `ops-provider-new.html`（新）
- 其他覆盖在 `platform-ops.html` / `platform-superadmin.html` / `provider-admin.html` 既有 sub-section

## 四、文档与基础设施

- PRD §20.4.1 实施层详述（数据模型 / API 清单 / 不变量 / 平台分成默认率表）
- `tests/test_alembic_roundtrip.py` 迁移 round-trip 安全网（upgrade head + 19001-19004 downgrade）
- `scripts/legal_conversion_smoke.py` 法务通道端到端冒烟脚本（13 步从下单到结算）
- `docs/UI_PROTOTYPE_GAPS.md` 全部缺口闭合（gap 报告归档为完成态）

## 五、关键不变量（验收必须满足）

1. ✅ JWT `jti` 字段保证同一秒登录的 token 唯一；旧 token hash 不在 `active_session` → 强制 401
2. ✅ L3 risk + tenant_settings.l3_hangup_enabled 双闸；既有调用方不开启时仅记录不挂断
3. ✅ 督导接管握手三态：request → agent_response_accept/reject；24h 未响应自动作废
4. ✅ 通知 dispatcher 内部 try/except，渠道失败不阻业务事务
5. ✅ `legal_conversion_order.platform_fee_amount` 在订单创建时冻结，律所/服务包后续变更不影响进行中的订单
6. ✅ `dispatch` 时 denormalize 律所/律师姓名快照；订单审计独立于律所池后续变更
7. ✅ `complete` 自增 `law_firm.completed_orders`；账单按 `completed_at` 落入对应账期
8. ✅ 文书模板 (tenant_id, package_type) 二级查找；占位缺失填 `[未填]` 而非崩溃
9. ✅ 同案件 active 转化订单去重（pending / dispatched / in_service 任一状态）→ 409
10. ✅ 多租户严格按 tenant_id 过滤所有 REST 查询；跨租户 404

## 六、已知约束

- 多 worker 部署 WS 状态：`_sessions` / `SupervisorManager._tenant_pools` 仍是进程内 dict；prod 升 N>1 worker 前需补 Redis pub/sub
- `promise_expiring` 通知：依赖 `CollectionCase.promise_due_at` 字段（暂未建模），扫描函数已 stub 优雅 no-op
- 律所外部账号体系：当前 dispatch 由平台 ops 代律所操作；律所自助接单（lawyer 角色登录）留 v1.6+
- PDF 渲染：当前文书生成产物为 markdown 文本；浏览器「打印 → 导出 PDF」可临时替代

## 七、迁移备忘

```bash
# DB 升级（19001-19004 共 4 条新迁移）
docker exec autoluyin-backend alembic upgrade head

# 验证（含 alembic round-trip）
docker exec autoluyin-backend pytest -q
# 应输出：524 passed

# 端到端冒烟（前端 + 后端运行后）
docker exec autoluyin-backend python -m scripts.api_smoke
docker exec autoluyin-backend python -m scripts.legal_conversion_smoke
```

## 八、回滚策略

- 应用层：法务转化通道仅 admin / ops 角色可见；如 PR 上线后发现严重问题，可禁用 admin 侧栏「法务转化」入口（`frontend/src/config/nav.ts`）+ 前端不影响其他模块
- DB 层：v1.5 4 张新表（19001-19004）支持纯 downgrade 回滚到 18002v14；已通过 round-trip 测试覆盖
- 数据：完成的法务订单和账单为业务历史数据，回滚前需评估是否保留快照
