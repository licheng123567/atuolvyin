# 账号体系合理化方案（v1.5 设计稿）

> 起源：v1.4 用户提问 — 平台 / 物业 / 服务商 / 项目服务人员各采用什么账号体系？
> 状态：**设计稿，待实施**（v1.5 起开工）

## 现状

当前 `UserAccount` 表只有 `phone_enc`（AES-256 手机号）+ `password_hash` 两个登录凭证，所有角色共用一种登录方式：手机号 + 密码。这有几个问题：

1. **物业/服务商的"组织账号"绑死个人手机号**：负责人离职后手机号失效或被回收，导致组织失去登录入口
2. **基层员工记密码累**：催收员/外勤经常忘密码，找物业 admin 重置成本高
3. **没有"账号 ≠ 手机号"的概念**：平台 ops 给物业公司发的"开通账号"应该是邮箱或工号，不该是某个员工的手机
4. **离职/合作终止后手动停用**：没有自动失效机制

## 推荐方案 — 三层账号体系

按"账号主体 = 谁负责保管这个登录"来分层：

### Layer 1：组织账号（Organization Account）

- **谁有**：每家物业公司（tenant）有 1 个；每家服务商（service_provider）有 1 个；每家律所有 1 个
- **登录凭证**：**邮箱 + 密码**（首次登录强制设置）
- **手机号**：**可绑定/换绑**，仅作 MFA + 找回密码用，**不是登录主键**
- **创建方**：平台 ops（手动开通，发激活链接到邮箱）
- **使用场景**：组织管理员（admin / provider_admin）登录，做大额操作（结算确认 / 解约 / 用户管理）
- **不变量**：邮箱**不可改**（改邮箱 = 换组织 = 走"组织迁移"流程，平台审批）；负责人离职 → 物业自己在系统内换绑邮箱 + 手机号，不触发停用

**为什么用邮箱**：邮箱归属公司域名（`admin@xinhua-property.com`），不会随个人离职流失；加 MFA 后安全性等同手机号。

### Layer 2：员工账号（Employee Account）

- **谁有**：每个组织内部的人（催收员 / 督导 / 法务 / 工单专员 / 项目经理 / 服务商外勤）
- **登录凭证**：**手机号 + 验证码（短信 OTP）** 为主，密码为辅（可选）
- **创建方**：组织管理员（物业 admin / 服务商 provider_admin）在自家后台批量录入手机号 + 姓名
- **首次登录**：发短信验证码 → 登录后系统提示设置密码（可选；不设也能用 OTP 登录）
- **使用场景**：日常作业（拨号 / 看案件 / 处理工单）

**为什么用手机+OTP**：
- 基层员工流动大，手机号是最低记忆门槛
- 短信运营成本可控（每次登录 ≤ 1 条 ≈ 0.05 元，单人月均不超过 30 通）
- 与 Android App 拨号绑定的手机号天然一致

### Layer 3：项目服务人员（Project Service Account）

> 这是 v1.4 用户问"项目服务人员用什么账号体系"——其实是 Layer 2 员工的子集

- **谁有**：被分配到具体项目的催收员（无论是物业内勤 `agent_internal` 还是服务商外勤 `agent_external`）
- **账号本身**：复用 Layer 2 员工账号
- **新增字段**：`UserTenantMembership` 加 `expire_at`、`access_hours` 字段（已存在）+ 新增 `project_scope JSONB`（指定可访问的 project_id 列表）
- **生命周期自动化**：
  - 项目结束（`Project.status='closed'`） → membership.is_active 自动转 false
  - 服务到期（`expire_at < now()`） → 同上
  - 服务商合作解约 → 该服务商所有外勤 membership 自动停用（连带 D3 的 30 天只读窗口）
  - 离职：组织管理员手动 PATCH `is_active=false`，触发审计 `user.deactivated`

**为什么不发独立账号**：服务商外勤可能同时服务 3 家物业，1 个手机号 + 多个 membership 比 3 个账号好管理。

## 数据库改动（v1.5 一条 alembic）

`user_account` 表：
```
+ email VARCHAR(120)  NULL  UNIQUE       # Layer 1 主登录
+ email_verified_at TIMESTAMPTZ NULL
+ phone_changed_at TIMESTAMPTZ NULL      # 手机号最后一次换绑时间，审计用
+ login_method VARCHAR(16) DEFAULT 'phone'   # 'phone' / 'email' / 'otp'
```

`user_tenant_membership` 表：
```
+ project_scope JSONB DEFAULT '[]'       # 限定可见 project_id（空数组 = 全部）
+ auto_expire_reason VARCHAR(32)         # 'project_closed' / 'contract_terminated' / 'manual'
```

## 登录路径分层

| URL | 主登录方式 | 兜底 |
|---|---|---|
| `/login` | 自动识别：手机号 → OTP；邮箱 → 密码 | 邮箱+密码 |
| `/login/admin`（物业/服务商管理员入口） | 邮箱+密码 | OTP |
| `/login/agent`（催收员入口，含 App） | 手机号+OTP | 手机号+密码 |
| `/login/ops`（平台运营/超管） | 邮箱+密码 + 强制 MFA | 无 |

## 离职/换绑流程

### 物业/服务商负责人离职

1. 旧负责人**仍能用邮箱登录**（账号是组织的，不是个人的）
2. 新负责人接手 → 在「我的账号」改 `email`（需当前邮箱二次验证）+ `phone`
3. 系统记一条 `audit_log: org.contact_changed`，发通知给平台 ops

### 员工离职

1. 物业 admin 在「用户管理」找到该员工 → 「停用」
2. 系统：`is_active=false`，立即吊销当前 session（active_session 表已有），ws 推 `user.deactivated`，App 端触发强退
3. 该员工历史通话/工单仍在系统（合规留档），但本人无法登录

### 项目结束

1. 物业 admin 关项目 → `Project.status='closed'`
2. worker 扫所有 `project_scope` 包含此 project_id 的 membership：
   - 若 membership 没有其他活跃项目 → `is_active=false`，`auto_expire_reason='project_closed'`
   - 否则 → 仅从 `project_scope` 移除该 project_id

## 工时估算（v1.5 一个独立 sprint）

| 子模块 | 工时 |
|---|---|
| Alembic + UserAccount/Membership 字段 | 0.5 天 |
| `/auth/login-by-otp`：发短信验证码 + 校验 | 1 天（含短信 mock） |
| 邮箱激活链接 + 邮箱密码登录 | 1 天 |
| 「我的账号」邮箱/手机换绑页（带二次验证） | 1.5 天 |
| `project_scope` 鉴权拦截层 | 1 天 |
| 离职 / 项目结束 worker（复用 v1.4 解约 worker 模式） | 0.5 天 |
| App 端登录改 OTP 优先 | 1 天 |
| 测试 + 文档 | 1.5 天 |

**总计 8 工作日 / 1.6 周**

## 决策点（待用户拍板）

1. **OTP 短信成本**：阿里云短信 ≈ 0.04 元/条；月单人 30 通 ≈ 1.2 元，10000 用户 = 12000/月。可接受？
2. **邮箱激活流程**：是 ops 创建后立即可用（弱安全）还是必须点邮件激活链接（强安全）？推荐后者。
3. **MFA 强制级别**：仅 ops + admin 强制 MFA，催收员选填？还是全员强制？推荐前者，避免 OTP 之外再加干扰。
4. **手机号唯一约束**：同一手机号能否在多个组织作员工？现状 phone_enc unique，需要解开。建议改成「手机号可在多个组织有 membership，但全局只对应 1 个 UserAccount」。
