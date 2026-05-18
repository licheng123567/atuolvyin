# 短信通道接入（OTP 验证码）设计文档

> 状态：设计已与用户确认（2026-05-18），待用户复审后转实施计划。

## 背景与目标

后端通知分发框架齐全，但短信渠道 `app/services/notifications/channels/sms.py` 是阿里云 stub（dev 仅 log、生产抛错），OTP 端点 `app/api/auth_extras.py` 的 `otp_send` / `password_reset_request` 只把验证码落库、未真正发短信（`# TODO: 接入 SMS gateway`）。

**目标**：接入第三方「短信中心」(028lk) API，让 OTP 验证码真正经短信送达；短信中心账号凭证、签名、OTP 模板由超级管理员在后台配置。

## 范围

**纳入**：
- OTP 验证码短信 —— 登录验证码（`otp_send`）+ 密码重置验证码（`password_reset_request`），二者同走 `_create_otp` 机制、共用一个 OTP 模板。
- 超级管理员配置短信中心：账号凭证 + 短信签名 + OTP 模板 ID。

**不在范围**：
- 通知类短信（配额告警 / 话术下线 / 工单完成 / 案件升级 / 承诺到期 5 类事件）—— `notifications/channels/sms.py` stub 保持原样不动。
- 向业主发送支付链接 —— 产品未确定。
- 邮箱 OTP（`_create_otp_email`，独立 email 渠道，不受影响）。
- 短信用量计费 / 限额。
- per-tenant 短信账号 —— 全平台共用一个短信中心账号。

## 第三方 API（短信中心 028lk）

- 文档：https://lkdoc.028lk.com/web/#/5/24
- 端点：`POST https://api.028lk.com/Sms/Api/Send`
- 鉴权：`SecretName`（API 密钥账户）+ `SecretKey`（鉴权凭证），明文鉴权（无需 `TimeStamp`）。
- 关键参数：`Mobile`（手机号）、`Content`（短信全文，≤500 字）、可选 `TemplateId` + `TemplateVars`（模板模式）、`SignName`（签名）。
- 响应：成功 `code=0` + `data`（短信批次号）；失败 `code` ≠ 0 + `msg`。
- 两种发送模式：① 直接文本（`Content` 传全文）② 模板（`TemplateId` + `TemplateVars` 替换占位符）。
- 鉴权与 `TemplateVars` 的精确字段格式见文档附录 —— 实施计划阶段按附录定稿。

## 架构

照搬代码库既有「超管配置外部服务」范式：`app/models/platform.py` 的 `BlockchainConfig`（单行平台级配置表、密钥 AES 加密存库、`/super/blockchain-config` 超管 GET/PUT、前端 `pages/super/blockchain-config/` 页）。

### ① 数据模型 `SmsConfig`

`app/models/platform.py` 新增单行平台级配置表（无 `tenant_id`），镜像 `BlockchainConfig`：

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | BigInteger PK | |
| `secret_name` | String | 短信中心 API 密钥账户 |
| `secret_key_enc` | Text, nullable | `SecretKey` 的 AES 密文（复用 `app.core.crypto.encrypt_phone` 通用 AES helper，与 `BlockchainConfig.api_key_enc` 同款）|
| `sign_name` | String | 短信签名（如「有证慧催」）|
| `otp_template_id` | String, nullable | OTP 验证码模板 ID；为空则走直接文本模式 |
| `is_active` | Boolean, default False | |
| `last_failure_at` | DateTime, nullable | 最近一次发送失败时间 |
| `last_failure_reason` | Text, nullable | 最近一次发送失败原因 |
| `updated_at` | DateTime | |

Alembic 迁移：新建 `sms_config` 表（迁移 revision 接当前 head）。

### ② 超管 API

`app/api/super_config.py` 新增两端点（与 `blockchain-config` 一模一样的写法）：
- `GET /super/sms-config` → `SmsConfigOut | None`
- `PUT /super/sms-config` → `SmsConfigOut`（upsert）

守卫 `require_roles("superadmin")`。Schema 放 `app/schemas/platform.py`：
- `SmsConfigIn`：`secret_name` / `secret_key`（可选，None 时不改）/ `sign_name` / `otp_template_id` / `is_active`。
- `SmsConfigOut`：暴露 `has_secret_key`（布尔，**不回传明文 key**）+ 其余字段 + `last_failure_*` + `updated_at`。

### ③ SMS 客户端 `app/services/sms_center.py`（新建）

单一公开函数：

```
send_otp_sms(db, *, phone: str, code: str) -> SmsResult
```

`SmsResult`：`ok: bool`、`batch_id: str | None`、`error: str | None`。

行为：
- 按 `settings.sms_backend` 分发（新增配置项，`"mock"` | `"sms_center"`，默认 `"mock"`）：
  - `mock`（dev / 测试默认）：只打 log（手机号脱敏 `138****1234`）、返回 `SmsResult(ok=True, batch_id="mock-...")`。测试强制此分支，绝不发真实 HTTP。
  - `sms_center`：读 `SmsConfig`（取最新一行）。无配置或 `is_active=False` → 返回 `SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")`。否则 `httpx.Client`（同步，带超时）POST 短信中心端点。
- **双模式**：`SmsConfig.otp_template_id` 非空 → 模板模式（`TemplateId` + `TemplateVars` 带验证码）；为空 → 直接文本模式（`Content` = 验证码文案，如「您的验证码是 {code}，5 分钟内有效，请勿泄露」）。
- 解析响应 `code==0` → `ok=True` + `batch_id`；否则 `ok=False` + `error`（短信中心 `msg`）。
- 发送失败时写回 `SmsConfig.last_failure_at` / `last_failure_reason`（与 `BlockchainConfig` 失败记录字段同款用途）。

### ④ OTP 链路接线

`app/api/auth_extras.py`：
- `otp_send`：`_create_otp` 之后调 `send_otp_sms(db, phone=body.phone, code=code)`。
- `password_reset_request`：用户存在分支里，`_create_otp` 之后同样调 `send_otp_sms`。
- `OTP_DEV_RETURN` / `dev_code` 行为保留（dev 仍直接返回 code 便于联调）。
- 失败处理：`settings.sms_backend == "sms_center"` 且 `send_otp_sms` 返回 `ok=False` → 抛 `403 {"code": "ERR_SMS_SEND_FAILED", "message": "验证码短信发送失败，请稍后重试"}`，让用户重试。`mock` 分支永远 `ok=True`，不影响 dev。
- `password_reset_request` 的「用户不存在仍假装成功」防爆破逻辑不变（不存在的用户不发短信）。

### ⑤ 前端

- 新增 `frontend/src/pages/super/sms-config/`，镜像 `pages/super/blockchain-config/` —— 表单字段：短信中心账户名、`SecretKey`（密码框，占位提示「已配置则留空不改」）、短信签名、OTP 模板 ID、启用开关。保存调 `PUT /super/sms-config`。
- 路由注册 + 超管 nav（`NAV_CONFIG.superadmin` 的「系统管理」区，紧挨「区块链配置」加「短信配置」）。

## 错误处理

- 端点错误响应沿用扁平 `{code, message}`。
- 新错误码：`ERR_SMS_SEND_FAILED`（OTP 短信发送失败，403）。
- `send_otp_sms` 内部不抛异常 —— 统一返回 `SmsResult`，由调用方决定是否转 HTTP 错误。

## 测试

- `SmsConfig` 模型 + 迁移：建表、单行 upsert。
- 超管 API：`GET` 空 / 有配置；`PUT` upsert；`SmsConfigOut` 不泄漏明文 `secret_key`（只 `has_secret_key`）；非超管 403。
- `send_otp_sms`：
  - `mock` 分支 → `ok=True`、不发 HTTP。
  - `sms_center` 分支 → 用 `httpx` 的 `MockTransport` 模拟 028lk 响应：`code=0` 成功路径、`code≠0` 失败路径、无 `SmsConfig` → `ERR_SMS_NOT_CONFIGURED`。
  - 模板模式（`otp_template_id` 配置）与直接文本模式各覆盖一次。
  - 失败时 `last_failure_*` 写回。
- OTP 接线：`otp_send` / `password_reset_request` 在 `mock` 下走通、`dev_code` 仍返回；`sms_center` + 模拟失败 → `ERR_SMS_SEND_FAILED`。
- 前端：sms-config 页渲染 + 表单提交（mirror blockchain-config 页测试）。
- 后端测试用 testcontainers；外部 HTTP 用 `httpx.MockTransport` 模拟（禁止打真实 028lk）。

## 风险

- 028lk 的明文鉴权具体签名方式与 `TemplateVars` 字段格式需在实施计划阶段对照文档附录定稿；若附录不足，实现时以最小可用参数集发一条，按真实返回校正。
- 国内验证码短信合规通常要求模板预先在短信中心控制台报备 —— 直接文本模式作兜底，但生产建议超管配置 `otp_template_id` 走模板模式。
- `secret_key` 以 AES 密文存库（与 `BlockchainConfig.api_key_enc` 同），`.env` 的 `autoluyin_aes_key` 是解密前提 —— 与既有约束一致。
