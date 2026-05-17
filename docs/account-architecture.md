# 账号体系

> 本文档包含两个部分：
> 1. **§ v2.2 角色模型重构**（当前有效设计，Tasks 1-10 已落地）
> 2. **§ v1.4 / v1.5 历史内容**（已被 v2.2 重构取代，仅作历史参考，其中的 11 角色枚举已废弃）

---

## v2.2 角色模型重构

> 实施于 `feature/role-model-refactor`，2026-05-16。设计权威文档：`docs/superpowers/specs/2026-05-16-role-model-refactor-design.md`。

### 四维正交模型

旧 11 角色枚举被拆分为四个正交维度，零冗余：

| 维度 | 落点 | 取值 |
|------|------|------|
| 平台身份 | `UserAccount.platform_role` | `superadmin` / `ops` / `NULL` |
| 组织职能 | `UserTenantMembership.role` | `admin` / `project_manager` / `supervisor` / `agent` / `legal` / `coordinator` |
| 组织归属 | `UserTenantMembership.provider_id` | `NULL` = 物业侧 / 非 `NULL` = 服务商侧 |
| 工作方式 | `UserTenantMembership.work_mode` | `internal` / `external`（仅 `agent` 角色；其余为 `NULL`） |

平台用户（`platform_role` 非 `NULL`）**无** tenant membership；JWT `scope` = `platform`。
物业侧用户 `provider_id = NULL`；JWT `scope` = `tenant:{tenant_id}`。
服务商侧用户 `provider_id` 非 `NULL`；JWT `scope` = `provider:{provider_id}`。

> 冗余字段 `UserTenantMembership.source_type`（旧 `INTERNAL`/`PROVIDER`）已随重构删除；组织归属统一由 `provider_id IS NULL` 判断。

### 衍生组合（零新增角色名）

| 业务身份 | role | provider_id | work_mode |
|---------|------|-------------|-----------|
| 物业管理员 | `admin` | NULL | NULL |
| 物业项目经理 | `project_manager` | NULL | NULL |
| 物业督导 | `supervisor` | NULL | NULL |
| 物业内勤催收员 | `agent` | NULL | `internal` |
| 物业外勤催收员 | `agent` | NULL | `external` |
| 物业法务 | `legal` | NULL | NULL |
| 物业工单协调员 | `coordinator` | NULL | NULL |
| 服务商管理员 | `admin` | set | NULL |
| 服务商项目经理 | `project_manager` | set | NULL |
| 服务商督导 | `supervisor` | set | NULL |
| 服务商催收员 | `agent` | set | `external` |
| 服务商法务（可选）| `legal` | set | NULL |
| 服务商工单协调员 | `coordinator` | set | NULL |

### 旧 11 角色 → 新模型映射

| 旧角色名（已废弃） | 新 role | provider_id | work_mode | platform_role |
|-----------------|---------|-------------|-----------|---------------|
| `admin` | `admin` | 不变（NULL）| NULL | — |
| `provider_admin` | `admin` | 不变（非空）| NULL | — |
| `supervisor` | `supervisor` | NULL | NULL | — |
| `agent_internal` | `agent` | NULL | `internal` | — |
| `agent_external` | `agent` | NULL | `external` | — |
| `legal` | `legal` | NULL | NULL | — |
| `coordinator` / `workorder` | `coordinator` | NULL | NULL | — |
| `project_manager_property` | `project_manager` | NULL | NULL | — |
| `project_manager_provider` | `project_manager` | 不变（非空）| NULL | — |
| `platform_ops`（membership 删除）| — | — | — | `ops` |
| `platform_superadmin` / `platform_super` | — | — | — | `superadmin` |

### Demo 账号（seed 密码统一 `Demo@123!`）

| 描述 | 手机号 | platform_role | role | provider_id | work_mode |
|------|--------|--------------|------|-------------|-----------|
| 平台超管 | 13000000000 | `superadmin` | — | — | — |
| 运营员 | 13000000001 | `ops` | — | — | — |
| 物业管理员 | 13000000002 | NULL | `admin` | NULL | NULL |
| 督导小李 | 13000000003 | NULL | `supervisor` | NULL | NULL |
| 内勤小张 | 13000000004 | NULL | `agent` | NULL | `internal` |
| 外勤小王 | 13000000005 | NULL | `agent` | NULL | `external` |
| 法务老周 | 13000000006 | NULL | `legal` | NULL | NULL |
| 协调员小赵 | 13000000007 | NULL | `coordinator` | NULL | NULL |
| 项目经理（物业）| 13000000008 | NULL | `project_manager` | NULL | NULL |
| 项目经理（服务商）| 13000000009 | NULL | `project_manager` | set | NULL |
| 服务商管理员 | 13000000010 | NULL | `admin` | set | NULL |
| 服务商催收员小孙 | 13000000011 | NULL | `agent` | set | `external` |
| 服务商督导小钱 | 13000000012 | NULL | `supervisor` | set | NULL |

### 端点鉴权守卫

- `require_tenant_roles(*roles)` — 仅物业侧（`provider_id IS NULL`），用于物业专用端点
- `require_provider_roles(*roles)` — 仅服务商侧（`provider_id IS NOT NULL`），用于服务商专用端点
- `require_roles(*roles)` — 不过滤归属侧，用于 `agent` 角色跨两侧的端点（凡角色元组含 `agent` 的端点必须用此守卫）

后端角色常量单一事实源：`app/core/roles.py`（禁止在其他文件散落角色字面量）。

---

## 历史内容（v1.4 已交付 + v1.5 演进）

> **注意**：以下内容描述的是 v2.2 重构之前的账号与角色体系（旧 11 角色枚举）。相关角色名已废弃，仅作历史参考。当前有效设计见上方 § v2.2 角色模型重构。

> 起源：v1.4 用户提问 — 平台 / 物业 / 服务商 / 项目服务人员各采用什么账号体系？

## 现状（v1.4）【已被 v2.2 重构取代，以下内容仅作参考】

`UserAccount` 表登录凭证字段（migration `22006v14`）：

```
phone_enc       AES-256 加密手机号  (唯一)        — 历史主登录入口
password_hash   bcrypt 密码哈希
email           邮箱（唯一，可空）                  — v1.4 新增，v1.5 转主登录
login_method    'phone' | 'email' | 'otp'         — 标记偏好登录方式
is_active       账号有效性
```

`Tenant.credit_code`（18 位统一社会信用代码，唯一可空）+ `ServiceProvider.credit_code`
作为组织级登录入口，无需绑定个人手机号。

`LoginOtp` 表存短信验证码（手机号、6 位 code、用途、5 分钟过期、60 秒频率限制）。

## 已实施登录方式（v1.4）

PC 登录页提供 **2 种 tab**（所有角色统一同一入口）：

### 方式 A：账号 + 密码 — `POST /auth/login-universal`

「账号」字段后端自动识别为以下 3 种之一：

| 输入 | 识别为 | 走的路径 |
|------|--------|---------|
| 11 位数字 | 手机号 | `phone_enc == encrypt_phone(account)` |
| 18 位 `[0-9A-Z]` | 统一社会信用代码 | 找 `Tenant.credit_code == account` 的第一个 admin |
| 含 `@` | 邮箱 | `UserAccount.email == account.lower()` |

### 方式 B：手机 + 短信验证码

- `POST /auth/otp/send` — 生成 6 位 OTP，写 `LoginOtp(purpose='login', expires_at=now+5min)`，dev 模式响应里直接回传 code
- `POST /auth/otp/verify` — 校验未消费 + 未过期 OTP → 标记 consumed → 发 token

### 忘记密码（v1.4）

`POST /auth/password-reset/request` → 发 OTP（用户不存在不报错防探测）
→ `POST /auth/password-reset/confirm` → 改密码

### 各角色推荐登录

| 角色 | 推荐 | 备选 |
|------|------|------|
| 平台超管 / 运营员 | 账号(手机/邮箱)+密码+TOTP MFA | — |
| 物业 admin | 账号(**信用代码**/手机/邮箱)+密码 | — |
| 服务商 admin | 账号(手机/邮箱)+密码 | — |
| 主管 / 内勤 / 法务 / 工单 / PM | 手机+OTP | 手机+密码 |
| 外勤（仅 App） | 手机+OTP | 手机+密码 |

## v1.5 演进项（设计完整稿）【历史路线图，部分已被 v2.2 重构覆盖】

> 以下为 v1.4 未实施部分，作为 v1.5 路线图。v2.2 角色重构已处理其中的组织归属、服务商侧角色等问题；`project_scope` / 离职 worker 等内容仍在后续待实施。

### 三层账号体系

按"账号主体 = 谁负责保管这个登录"分层：

#### Layer 1：组织账号（Organization Account）

- **谁有**：每家物业（tenant）/ 服务商（service_provider）/ 律所各 1 个
- **登录凭证**：**邮箱 + 密码**（首次登录强制设置）
- **手机号**：**可绑定/换绑**，仅作 MFA + 找回密码用，**不是登录主键**
- **创建方**：平台 ops（手动开通，发激活链接到邮箱）
- **使用场景**：组织管理员（admin / provider_admin）登录，做大额操作
- **不变量**：邮箱**不可改**（改邮箱 = 换组织 = 走平台审批的"组织迁移"流程）；负责人离职 → 物业自己在系统内换绑邮箱 + 手机号，不触发停用

**为什么用邮箱**：邮箱归属公司域名（`admin@xinhua-property.com`），不会随个人离职流失；加 MFA 后安全性等同手机号。

#### Layer 2：员工账号（Employee Account）

- **谁有**：组织内部的人（催收员 / 督导 / 法务 / 工单 / 项目经理 / 服务商外勤）
- **登录凭证**：**手机 + OTP** 为主，密码为辅
- **创建方**：组织管理员在自家后台批量录入手机 + 姓名
- **首次登录**：发 OTP → 登录后系统提示设置密码（可选）
- **使用场景**：日常作业（拨号 / 看案件 / 处理工单）

**为什么用手机+OTP**：
- 基层员工流动大，手机号是最低记忆门槛
- 短信成本可控（≤ 0.05 元/次，单人月均 ≤ 30 通）
- 与 Android App 拨号绑定的手机号天然一致

#### Layer 3：项目服务人员（Project Service Account）

- **谁有**：被分配到具体项目的催收员（内勤 `agent_internal` 或外勤 `agent_external`）
- **账号本身**：复用 Layer 2 员工账号
- **新增字段**（v1.5）：`UserTenantMembership.project_scope JSONB`（指定可访问的 project_id 列表，空数组 = 全部）
- **生命周期自动化**（v1.5 worker）：
  - 项目结束（`Project.status='closed'`） → membership.is_active 自动转 false
  - 服务到期（`expire_at < now()`） → 同上
  - 服务商合作解约 → 该服务商所有外勤 membership 自动停用（已在 v1.4 通过 `terminated_at` + 30 天只读窗口落实）
  - 离职：组织管理员手动 PATCH `is_active=false`，触发审计 `user.deactivated`

**为什么不发独立账号**：服务商外勤可能同时服务 3 家物业，1 个手机号 + 多个 membership 比 3 个账号好管理。

### v1.5 数据库改动（一条 alembic）

`user_account`：
```
+ email_verified_at TIMESTAMPTZ NULL          # 邮箱激活时间戳（v1.4 已有 email 字段）
+ phone_changed_at TIMESTAMPTZ NULL           # 手机号最后一次换绑时间，审计用
```

`user_tenant_membership`：
```
+ project_scope JSONB DEFAULT '[]'            # 限定可见 project_id（空 = 全部）
+ auto_expire_reason VARCHAR(32)              # 'project_closed' / 'contract_terminated' / 'manual'
```

### v1.5 登录路径分层（多入口）

| URL | 主登录方式 | 兜底 |
|---|---|---|
| `/login` | 账号密码（自动识别）/ 手机 OTP | — |
| `/login/admin` | 邮箱+密码（强制 MFA） | OTP |
| `/login/agent`（PC + App） | 手机+OTP | 手机+密码 |
| `/login/ops`（平台后台） | 邮箱+密码+TOTP | — |

### 离职/换绑流程

#### 物业/服务商负责人离职

1. 旧负责人**仍能用邮箱登录**（账号是组织的，不是个人的）
2. 新负责人接手 → 在「我的账号」改 `email`（需当前邮箱二次验证）+ `phone`
3. 系统记一条 `audit_log: org.contact_changed`，发通知给平台 ops

#### 员工离职

1. 物业 admin 在「用户管理」找到该员工 → 「停用」
2. `is_active=false`，立即吊销当前 session，ws 推 `user.deactivated`，App 强退
3. 历史通话/工单仍在系统（合规留档），本人无法登录

#### 项目结束（v1.5 worker）

1. 物业 admin 关项目 → `Project.status='closed'`
2. worker 扫所有 `project_scope` 包含此 project_id 的 membership：
   - 若 membership 没有其他活跃项目 → `is_active=false`，`auto_expire_reason='project_closed'`
   - 否则 → 仅从 `project_scope` 移除该 project_id

## v1.5 工时估算

| 子模块 | 工时 |
|---|---|
| Alembic + UserAccount/Membership 新字段 | 0.5 天 |
| 邮箱激活链接（首次设密 + 后续登录） | 1 天 |
| 「我的账号」邮箱/手机换绑页（带二次验证） | 1.5 天 |
| `project_scope` 鉴权拦截层 | 1 天 |
| 项目结束 / 离职 worker（复用 v1.4 解约 worker 模式） | 0.5 天 |
| App 端登录改 OTP 优先 | 1 天 |
| 测试 + 文档 | 1.5 天 |

**总计约 7 工作日 / 1.4 周**（v1.4 已落地 OTP 短信通道与登录端点，节省约 1 天）

## 决策点（v1.5 启动前需拍板）

1. **OTP 短信成本**：阿里云短信 ≈ 0.04 元/条；月单人 30 通 ≈ 1.2 元，10000 用户 = 12000/月。可接受？
2. **邮箱激活流程**：是 ops 创建后立即可用（弱安全）还是必须点邮件激活链接（强安全）？推荐后者。
3. **MFA 强制级别**：仅 ops + admin 强制 MFA，催收员选填？还是全员强制？推荐前者。
4. **手机号唯一约束**：同一手机号能否在多个组织作员工？现状 `phone_enc unique`，需要解开 — 建议改成「手机号可在多个组织有 membership，但全局只对应 1 个 UserAccount」。
