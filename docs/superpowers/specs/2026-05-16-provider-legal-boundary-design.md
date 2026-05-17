# §9.1 服务商法务职责边界 — 设计文档

> 来源：`docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` §9「下游影响」第 1 项。
> §9 三项下游需求的第二个（§9.3 已完成 → **§9.1** → §9.2）。

**日期：** 2026-05-16
**分支：** `feat/v2.2-app-ux-fixes`

---

## 1. 问题陈述

角色模型重构后，服务商侧法务用户（`UserTenantMembership.role='legal'` 且 `provider_id` 非空）在数据模型上已能表达，但**所有法务端点都用 `require_tenant_roles` 守卫（断言 `provider_id IS NULL`），服务商侧 legal 用户连不进任何法务端点** —— 现状是「完全锁死」。

角色模型 spec §9.1 已拍板服务商法务的职责边界：

- 职责限于**整理催收材料、发起法务转化请求、跟进进度**。
- 物业费债权人是物业公司，**审批权、诉讼主体、终审决定权始终在物业** —— 服务商法务不得审批、不得处理物业内部法务订单、不得派律所、不得签发文书。
- 服务商法务**可选** —— 小服务商无法务时催收员直接发起请求；seed 不强制造此账号。

本设计把这条边界**落成可用的代码** —— 既开放允许的子集，又用结构性隔离堵死其余。

### 范围

- **新增** 服务商法务可用的端点（案件只读浏览、上传补充材料、发起转化请求、跟进进度）。
- **新增** 一张材料附件表。
- 物业侧让审批人看得到材料（补 2 个物业侧端点）。
- 物业侧既有 legal 端点（审批/拒绝、内部订单处理、律所/律师工作台、文书）**完全不动**。
- 不改角色模型、不改 JWT、不改 `LegalConversionRequest` 既有字段。

---

## 2. 架构

新建路由文件 `poc/backend/app/api/provider_legal.py`，**整个路由统一用 `require_provider_roles("legal")` 守卫**。

- `require_provider_roles`（`app/core/security.py`）已存在、当前无人使用：断言角色匹配 + `provider_id IS NOT NULL`。物业侧 legal、服务商侧非 legal、平台用户全部被它挡在外面。
- 与现有 `/agent/*`、`/lawfirm/*`、`/lawyer/*`、`/admin/*` 分面模式一致 —— **无双模式端点**，服务商侧与物业侧各走各的路由，杜绝守卫分支泄漏。
- 「服务商法务不得做的事」靠**结构性隔离**实现：那些能力的端点根本不在新路由里，无需新增任何拒绝逻辑。

物业侧补 2 个端点放进既有 `app/api/legal_conversion_requests.py`（审批人看材料用），守卫仍是 `require_tenant_roles`。

---

## 3. 数据模型

### 3.1 新表 `legal_conversion_request_material`

补充材料附在「法务转化请求」上 —— 一个请求是服务商法务为某案件整理的「提交包」，材料随请求走，生命周期清晰。

新增 ORM 模型 `LegalConversionRequestMaterial`（放进 `poc/backend/app/models/legal_conversion.py`）：

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | BigInteger PK | |
| `request_id` | BigInteger FK → `legal_conversion_request.id` `ON DELETE CASCADE`，非空，索引 | 所属请求 |
| `tenant_id` | BigInteger FK → `tenant.id` `ON DELETE CASCADE`，非空，索引 | 多租户规则：每表带 tenant_id |
| `object_key` | Text 非空 | MinIO 对象键 |
| `filename` | Text 非空 | 原始文件名 |
| `content_type` | Text 可空 | MIME |
| `size_bytes` | Integer 可空 | 文件大小 |
| `uploaded_by` | BigInteger FK → `user_account.id` `ON DELETE RESTRICT`，非空 | 上传人 |
| `created_at` / `updated_at` | `TimestampMixin` | |

**不加 `provider_id` 列** —— 归属通过 `material → request → case → project.provider_id` 传递推导；`uploaded_by` 亦可溯源。与角色模型 spec §9.1「零新增」一致。

### 3.2 Alembic 迁移

新增一条迁移建此表，`down_revision = "24016v220b"`（当前 head，`alembic heads` 已确认）。`upgrade()` 建表 + 两个索引（`request_id`、`tenant_id`）；`downgrade()` drop 表，完整可逆。ORM `__table_args__` 与迁移保持一致。

### 3.3 `LegalConversionRequest` 不动

请求仍直接建为 `status='pending'`（既有 CHECK 约束 `status IN ('pending','approved','rejected','cancelled')` 不变）。材料在 `pending` 期可传，审批后锁定。

---

## 4. 端点清单

所有路径前缀 `/api/v1/`。所有响应错误格式 `{"code": "ERR_XXX", "message": "..."}`。

### 4.1 `/provider/legal/*` —— 7 个，全部 `require_provider_roles("legal")`

| # | 方法 + 路径 | 作用 |
|---|------------|------|
| 1 | `GET /provider/legal/cases` | 分页列出本服务商**有效项目**下的案件 |
| 2 | `GET /provider/legal/cases/{case_id}` | 案件只读详情（含通话/证据概览）|
| 3 | `POST /provider/legal/cases/{case_id}/conversion-request` | 发起法务转化请求 |
| 4 | `POST /provider/legal/conversion-requests/{request_id}/materials` | 上传补充材料（multipart）|
| 5 | `GET /provider/legal/conversion-requests/{request_id}/materials/{material_id}` | 取材料下载链接 |
| 6 | `GET /provider/legal/conversion-requests` | 列出本服务商的请求 + 订单高阶状态 |
| 7 | `GET /provider/legal/conversion-requests/{request_id}` | 请求详情 + 材料列表 + 订单高阶状态 |

**端点 1 — 案件列表**：分页（复用既有 `PaginatedResponse`）。每项返回 `case_id`、业主姓名、业主电话（脱敏，见 §6）、`amount_owed`、`months_overdue`、`stage`、`project_id`/`project_name`。WHERE = §5 的案件可见性子句。

**端点 2 — 案件详情**：返回案件字段 + 业主信息（电话脱敏）+ 通话记录概览（条数/最近时间）+ 已有证据概览。案件不在本服务商可见范围 → `404 ERR_NOT_FOUND`（不泄漏存在性）。

**端点 3 — 发起转化请求**：Body `{"reason": str}`（Pydantic schema，`reason` 可空）。校验：
- 案件须在本服务商可见范围，否则 `404`。
- 沿用既有防重（参照 `agent_cases.py` intent 流）：该 `case_id` 已有活跃 `LegalConversionOrder`（status ∈ `pending|dispatched|in_service`）或已有 `pending` 的 `LegalConversionRequest` → `409 ERR_CONFLICT`。
- 建 `LegalConversionRequest(tenant_id, case_id, requester_user_id=<当前用户>, requester_role="legal", reason, status="pending")`。
- 写审计日志 `legal_conversion_request.created`（对齐 `agent_cases.py` 现有写法）。
- 返回新建请求。

**端点 4 — 上传材料**：multipart（`file: UploadFile`）。校验：
- 请求须属本服务商（见 §5），否则 `404`。
- 请求 `status` 须为 `pending`，否则 `409 ERR_CONFLICT`（「请求已审批，材料锁定」）。
- 空文件 `422 ERR_EMPTY_FILE`；超 `MAX_DOC_SIZE`（复用 `legal_documents.py` 的 50MB 常量）`413 ERR_FILE_TOO_LARGE`；MIME 不在允许前缀 `422 ERR_INVALID_MIME`。
- 对象键 `legal_conv_req_materials/{tenant_id}/{request_id}/{uuid}.{ext}`，`storage.put_object(...)`；存储失败 `502 ERR_STORAGE_FAILURE`。
- 落 `LegalConversionRequestMaterial` 行，返回该行。

**端点 5 — 下载材料**：材料须属本服务商的请求，否则 `404`。返回 `{"download_url": <presigned>, "filename", "content_type", "size_bytes", "expires_in_sec": 3600}`（复用 `storage.get_url`，与 `legal_documents.py` 下载一致）。

**端点 6 — 请求列表**：分页。每项 = 请求字段（`id`、`case_id`、`status`、`reason`、`created_at`、`reviewed_at`、`reviewer_note`）+ `order_status`（`related_order_id` 对应 `LegalConversionOrder.status`，无单则 `null`）。WHERE = 请求的 `case` 在本服务商项目内（见 §5）。

**端点 7 — 请求详情**：请求字段 + `materials: [{id, filename, content_type, size_bytes, created_at}]` + `order_status`（高阶状态字段，**不含**物业内部处理动作明细）。不属本服务商 → `404`。

### 4.2 物业侧补 2 个 —— 放进 `legal_conversion_requests.py`，`require_tenant_roles("supervisor","admin","superadmin")`

| # | 方法 + 路径 | 作用 |
|---|------------|------|
| 8 | `GET /legal-conversion-requests/{request_id}` | 物业审批人看请求详情 + 材料列表 |
| 9 | `GET /legal-conversion-requests/{request_id}/materials/{material_id}` | 物业侧取材料下载链接 |

守卫角色元组与既有 `approve`/`reject` 端点一致。`tenant_id` 作用域校验（请求 `tenant_id` ≠ token tenant → `404`）。端点 8 响应结构与端点 7 对齐（请求字段 + materials + order_status）。端点 9 与端点 5 响应结构一致。

> 端点 8/9 是「让审批人看得到材料」的必要配套 —— 材料若审批人看不到就失去意义。用户已明确：不精简、不推迟。

---

## 5. 数据隔离

CLAUDE.md 硬规则：服务商数据按 `provider_id` 隔离；所有查询带 `tenant_id`。

**案件可见性子句**（在 `provider_legal.py` 内写一个小过滤函数 `_provider_legal_case_filter(tenant_id, provider_id)`，返回 SQLAlchemy 子句）：

```
CollectionCase.tenant_id == tenant_id
AND CollectionCase.project_id IN (
    SELECT Project.id WHERE
        Project.tenant_id == tenant_id
        AND Project.provider_id == provider_id
        AND Project.status == 'active'
        AND (Project.plan_end IS NULL OR Project.plan_end >= now())
)
```

复用既有 `Project.provider_id` 归属口径（与 `agent_cases.py` 的外勤可见性同源）。法务不像催收员被指派具体案件，故**不再按 `assigned_to` 细分** —— 本服务商有效项目下的案件法务都可只读浏览。

**请求/材料归属**：请求归服务商 P ⟺ 其 `case_id` 对应的案件在 P 的项目内。按 `LegalConversionRequest → CollectionCase → Project.provider_id` join 过滤（比 `requester_user_id` 更稳 —— 发起人离职也不影响归属）。材料经 `request_id` 继承请求的归属。`provider_id` 与 `tenant_id` 均取自 JWT payload。

---

## 6. 电话可见性

服务商法务看到的业主电话**一律脱敏**（`138****1234`）。

`should_reveal_owner_phone`（`app/core/phone_visibility.py`）对 `role == 'legal'` 的判定只看 `legal_case_stage` 是否在 `LEGAL_ACTIVE_STAGES`，与 `provider_id` 无关。本路由处理的是**转化前的普通 `CollectionCase`**，无 `LegalCase.stage`，故传 `legal_case_stage=None` → 不在活跃阶段 → 脱敏。整理材料阶段不需要明文电话；明文留给真正进入诉讼阶段后。

调用方式：`display_owner_phone(owner.phone_enc, reveal=should_reveal_owner_phone(role="legal", provider_id=<P>, legal_case_stage=None))`，等价于固定脱敏。设计上仍走 `should_reveal_owner_phone` 而非硬编码 —— 保持电话可见性策略单一入口。

---

## 7. 安全影响

- 改动方向是**受控开放**：服务商法务从「完全锁死」变为「能做被批准的 4 件事」，其余仍锁死。
- 「服务商法务不得做的事」靠结构性隔离（不在新路由里）实现，不依赖运行时分支判断 —— 不存在守卫写错导致越权的面。
- `require_provider_roles("legal")` 确保只有 `provider_id` 非空 + 角色 legal 的用户进得来；物业侧 legal（`provider_id` 为空）被挡。
- 跨服务商隔离由 §5 的 `Project.provider_id` 子句保证 —— 服务商 A 的法务查询里永远带 `provider_id == A`。
- 审批权未被触碰：`approve`/`reject` 仍是 `require_tenant_roles`，服务商法务无法染指。
- 业主电话脱敏，AES-256 密文不落 payload。

---

## 8. 测试

DB 集成测试用 testcontainers-postgres，禁止 mock 数据库。

**鉴权守卫：**
- 物业侧 legal（`provider_id` 空）访问 `/provider/legal/*` → `403`。
- 服务商侧非 legal（如服务商 agent）访问 `/provider/legal/*` → `403`。
- 无 token / 角色不符 → `401/403`。

**跨服务商隔离：**
- 服务商 A 的法务 `GET /provider/legal/cases` 只见 A 项目下案件，不见 B 的。
- A 的法务 `GET /provider/legal/cases/{B的案件}` → `404`。
- A 的法务 `GET /provider/legal/conversion-requests/{B的请求}` → `404`。

**发起请求：**
- 正常发起 → `LegalConversionRequest` 落库，`requester_role="legal"`、`status="pending"`、`requester_user_id` 正确；审计日志写入。
- 案件已有活跃订单 / 已有 pending 请求 → `409`。
- 案件不在本服务商范围 → `404`。

**材料上传/下载：**
- 上传 → `LegalConversionRequestMaterial` 落库 + 对象进存储；`uploaded_by` 正确。
- 下载 → 返回可用 `download_url`。
- 请求非 `pending` 期上传 → `409`。
- 空文件 → `422`；超限 → `413`。
- 跨服务商请求上传/下载 → `404`。

**跟进进度：**
- 请求列表/详情返回正确 `status`；关联订单存在时 `order_status` 反映 `LegalConversionOrder.status`，无单为 `null`。

**物业侧端点 8/9：**
- 物业审批人 `GET /legal-conversion-requests/{id}` 看到请求详情 + 材料列表，能下载。
- 跨 tenant 的请求 → `404`。
- 服务商侧用户访问端点 8/9（`require_tenant_roles`）→ `403`。

**电话可见性：**
- `/provider/legal/cases` 与案件详情返回的业主电话为 `138****1234` 形式。

---

## 9. 文件清单

| 文件 | 操作 |
|------|------|
| `poc/backend/app/api/provider_legal.py` | 建：7 个 `/provider/legal/*` 端点 + `_provider_legal_case_filter` |
| `poc/backend/app/models/legal_conversion.py` | 改：新增 `LegalConversionRequestMaterial` 模型 |
| `poc/backend/alembic/versions/24017_v220_legal_conv_req_material.py` | 建：建表迁移（`down_revision="24016v220b"`）|
| `poc/backend/app/schemas/` | 改/建：provider-legal 端点的 Pydantic schema（案件列表项/详情、请求创建入参、请求列表/详情出参、材料出参、下载出参）|
| `poc/backend/app/api/legal_conversion_requests.py` | 改：补端点 8/9（物业侧请求详情 + 材料下载）|
| `poc/backend/app/main.py` | 改：注册 `provider_legal` router |
| `poc/backend/tests/api/test_provider_legal.py` | 建：§8 全部测试用例 |
| `poc/backend/tests/api/test_legal_conversion_requests.py` | 改：补端点 8/9 测试 |
| `docs/superpowers/specs/2026-05-16-role-model-refactor-design.md` | 改：§9.1 标注「已实现，见本文档」|

无前端 / Android 改动（本期只交付后端能力；前端接入是后续独立工作）。
