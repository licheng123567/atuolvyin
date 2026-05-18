# 短信通道接入（OTP 验证码）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 接入「短信中心」(028lk) API，让 OTP 验证码（登录 + 密码重置）真正经短信送达；短信中心账号 / 签名 / 模板由超级管理员后台配置。

**Architecture:** 照搬代码库既有「超管配置外部服务」范式（`BlockchainConfig` 模型 + `/super/blockchain-config` 端点 + `pages/super/blockchain-config/` 页）。新增单行平台级 `SmsConfig` 配置表（密钥 AES 加密存库）、超管 GET/PUT 端点、`sms_center.py` 客户端（按 `settings.sms_backend` 分发 mock/真实 HTTP）、OTP 端点接线、超管前端配置页。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL + httpx（后端）；React + TypeScript + Refine.dev（前端）；pytest + testcontainers / Vitest（测试）。

设计依据：`docs/superpowers/specs/2026-05-18-sms-otp-channel-design.md`。

**关键事实（实现前必读）：**
- 测试 conftest（`poc/backend/tests/conftest.py:30`）用 `Base.metadata.create_all` 建表 —— 模型是测试事实源；Alembic 迁移作用于真实 DB，两者须一致。
- 当前 Alembic head 是 `24019v220e`。
- `app.core.crypto` 有通用 AES helper `encrypt_phone` / `decrypt_phone`（`super_config.py` 用 `encrypt_phone` 加密 blockchain api_key，称其「generic AES helper」）。
- `httpx` 已是依赖（`app/services/mipush_xiaomi.py` 在用）。
- `super_config.py` 已注册进 app（blockchain-config 端点可用），新增 SMS 端点写进同文件即可，无需注册新 router。
- 028lk 端点 `POST https://api.028lk.com/Sms/Api/Send`，明文鉴权（`SecretName`+`SecretKey` 直接放 JSON body，无需签名 / `TimeStamp`）。请求体字段：`SecretName`/`SecretKey`/`Mobile`/`Content`/`TemplateId`/`TemplateVars`（String 数组）/`SignName`（格式 `【签名】`）。响应 `{"code":0,"msg":null,"data":"<批次号>"}`，`code==0` 为成功。
- `OTP_TTL_SECONDS = 300`（5 分钟），定义在 `app/api/auth_extras.py`。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `poc/backend/app/models/platform.py` | 平台级模型 | 改：加 `SmsConfig` 类 |
| `poc/backend/alembic/versions/24020_v220_sms_config.py` | 迁移 | 新建 |
| `poc/backend/app/schemas/platform.py` | 平台 schema | 改：加 `SmsConfigIn` / `SmsConfigOut` |
| `poc/backend/app/api/super_config.py` | 超管配置端点 | 改：加 `GET`/`PUT /super/sms-config` |
| `poc/backend/app/core/config.py` | 应用配置 | 改：加 `sms_backend` 字段 |
| `poc/backend/app/services/sms_center.py` | 短信客户端 | 新建 |
| `poc/backend/app/api/auth_extras.py` | OTP 端点 | 改：`otp_send` / `password_reset_request` 接线 |
| `frontend/src/pages/super/sms-config/index.tsx` | 超管短信配置页 | 新建 |
| `frontend/src/App.tsx` | 路由 | 改：注册 `/super/sms-config` |
| `frontend/src/config/nav.ts` | 导航 | 改：超管 nav 加「短信配置」|
| 测试文件 | | 新建 / 改（各 Task 内列出）|

---

## Task 1: `SmsConfig` 模型 + Alembic 迁移

**Files:**
- Modify: `poc/backend/app/models/platform.py`
- Create: `poc/backend/alembic/versions/24020_v220_sms_config.py`
- Test: `poc/backend/tests/api/test_sms_config_model.py`

- [ ] **Step 1: 写失败测试** — 创建 `poc/backend/tests/api/test_sms_config_model.py`：

```python
"""短信通道 Task 1 — SmsConfig 模型测试。"""
from __future__ import annotations

import sqlalchemy as sa

from app.models.platform import SmsConfig


def test_sms_config_insert_and_query(db_session):
    cfg = SmsConfig(
        secret_name="API",
        secret_key_enc="enc-xxx",
        sign_name="有证慧催",
        otp_template_id="T1001",
        is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()
    row = db_session.execute(sa.select(SmsConfig)).scalar_one()
    assert row.secret_name == "API"
    assert row.sign_name == "有证慧催"
    assert row.otp_template_id == "T1001"
    assert row.is_active is True
    assert row.last_failure_at is None


def test_sms_config_optional_fields_nullable(db_session):
    """secret_key_enc / otp_template_id / last_failure_* 可空。"""
    cfg = SmsConfig(secret_name="API2", sign_name="测试签名")
    db_session.add(cfg)
    db_session.flush()
    row = db_session.execute(
        sa.select(SmsConfig).where(SmsConfig.secret_name == "API2")
    ).scalar_one()
    assert row.secret_key_enc is None
    assert row.otp_template_id is None
    assert row.is_active is False
```

> `db_session` 是 `tests/conftest.py` 既有 fixture。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_sms_config_model.py -q`
Expected: FAIL —— `cannot import name 'SmsConfig'`。

- [ ] **Step 3: 加模型** — `poc/backend/app/models/platform.py`，在 `BlockchainConfig` 类之后追加（镜像 `BlockchainConfig` 结构）：

```python
class SmsConfig(Base):
    """短信中心（028lk）平台级配置 —— 单行，超管在 /super/sms-config 维护。"""

    __tablename__ = "sms_config"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    secret_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    secret_key_enc: Mapped[str | None] = mapped_column(sa.Text, nullable=True)  # AES-256
    sign_name: Mapped[str] = mapped_column(sa.String(64), nullable=False, default="")
    otp_template_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    last_failure_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
```

> `datetime` / `Mapped` / `mapped_column` / `sa` / `Base` 在 `platform.py` 顶部已 import（`BlockchainConfig` 用了同款）。确认无需新增 import。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_sms_config_model.py -q`
Expected: PASS（2 passed）。

- [ ] **Step 5: 写 Alembic 迁移** — 创建 `poc/backend/alembic/versions/24020_v220_sms_config.py`：

```python
"""短信通道 — sms_config 平台级配置表

Revision ID: 24020v220f
Revises: 24019v220e
Create Date: 2026-05-18 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24020v220f"
down_revision: str | None = "24019v220e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sms_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("secret_name", sa.String(length=128), nullable=False),
        sa.Column("secret_key_enc", sa.Text(), nullable=True),
        sa.Column("sign_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("otp_template_id", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sms_config")
```

- [ ] **Step 6: 校验迁移可加载**

Run: `cd poc/backend && python3.12 -c "import importlib.util, pathlib; p = pathlib.Path('alembic/versions/24020_v220_sms_config.py'); s = importlib.util.spec_from_file_location('m', p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); print('revision', m.revision, 'down', m.down_revision)"`
Expected: 打印 `revision 24020v220f down 24019v220e`，无异常。

- [ ] **Step 7: ruff + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/models/platform.py alembic/versions/24020_v220_sms_config.py tests/api/test_sms_config_model.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/models/platform.py poc/backend/alembic/versions/24020_v220_sms_config.py poc/backend/tests/api/test_sms_config_model.py
git commit -m "feat(sms): SmsConfig 平台级配置表 + 迁移"
```

---

## Task 2: 超管 API `GET`/`PUT /super/sms-config`

**Files:**
- Modify: `poc/backend/app/schemas/platform.py`
- Modify: `poc/backend/app/api/super_config.py`
- Test: `poc/backend/tests/api/test_super_config.py`

- [ ] **Step 1: 写失败测试** — 在 `poc/backend/tests/api/test_super_config.py` 末尾追加（沿用文件既有 `client: AsyncClient` + `super_auth_headers` fixture 风格；另需一个非超管 headers —— 先 `grep -n "auth_headers\|admin_auth" tests/api/test_super_config.py tests/conftest.py tests/api/conftest.py` 找既有非超管 fixture，没有就用文件里已有的任意非超管角色 fixture）：

```python
# ── 短信配置 ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sms_config_get_empty(client, super_auth_headers):
    r = await client.get("/api/v1/super/sms-config", headers=super_auth_headers)
    assert r.status_code == 200
    assert r.json() is None


@pytest.mark.asyncio
async def test_sms_config_put_then_get(client, super_auth_headers):
    put = await client.put(
        "/api/v1/super/sms-config",
        json={
            "secret_name": "API",
            "secret_key": "s3cr3t",
            "sign_name": "有证慧催",
            "otp_template_id": "T1001",
            "is_active": True,
        },
        headers=super_auth_headers,
    )
    assert put.status_code == 200
    body = put.json()
    assert body["secret_name"] == "API"
    assert body["sign_name"] == "有证慧催"
    assert body["otp_template_id"] == "T1001"
    assert body["is_active"] is True
    assert body["has_secret_key"] is True
    # 明文 secret_key 绝不回传
    assert "secret_key" not in body
    assert "secret_key_enc" not in body

    got = await client.get("/api/v1/super/sms-config", headers=super_auth_headers)
    assert got.json()["secret_name"] == "API"


@pytest.mark.asyncio
async def test_sms_config_put_upsert_keeps_key_when_omitted(client, super_auth_headers):
    """secret_key 传 null 时不改原 key（has_secret_key 仍 True）。"""
    await client.put(
        "/api/v1/super/sms-config",
        json={"secret_name": "API", "secret_key": "k1", "sign_name": "S",
              "otp_template_id": None, "is_active": False},
        headers=super_auth_headers,
    )
    r = await client.put(
        "/api/v1/super/sms-config",
        json={"secret_name": "API2", "secret_key": None, "sign_name": "S2",
              "otp_template_id": None, "is_active": True},
        headers=super_auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["secret_name"] == "API2"
    assert r.json()["has_secret_key"] is True


@pytest.mark.asyncio
async def test_sms_config_requires_superadmin(client, agent_auth_headers):
    """非超管访问 → 403。agent_auth_headers 换成测试文件里实际可用的非超管 fixture。"""
    r = await client.get("/api/v1/super/sms-config", headers=agent_auth_headers)
    assert r.status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_super_config.py -q -k sms`
Expected: FAIL —— 端点不存在（404）。

- [ ] **Step 3: 加 schema** — `poc/backend/app/schemas/platform.py`，在 `BlockchainConfigOut` 之后追加：

```python
class SmsConfigIn(BaseModel):
    secret_name: str = Field(min_length=1, max_length=128)
    secret_key: str | None = Field(None, max_length=500)  # None=不改
    sign_name: str = Field(default="", max_length=64)
    otp_template_id: str | None = Field(None, max_length=64)
    is_active: bool = False


class SmsConfigOut(BaseModel):
    id: int
    secret_name: str
    sign_name: str
    otp_template_id: str | None
    has_secret_key: bool  # never echo the key back
    is_active: bool
    last_failure_at: datetime | None
    last_failure_reason: str | None
    updated_at: datetime
```

> `BaseModel` / `Field` / `datetime` 在 `platform.py` 顶部已 import（`BlockchainConfig*` schema 用了同款）。确认无需新增。

- [ ] **Step 4: 加端点** — `poc/backend/app/api/super_config.py`。import 区把 `from app.models.platform import BlockchainConfig, LLMPromptTemplate` 改为 `from app.models.platform import BlockchainConfig, LLMPromptTemplate, SmsConfig`；`from app.schemas.platform import (...)` 里加 `SmsConfigIn, SmsConfigOut`。文件末尾追加：

```python
# ── 短信中心配置 ─────────────────────────────────────────────────────


def _sms_config_to_out(c: SmsConfig) -> SmsConfigOut:
    return SmsConfigOut(
        id=c.id,
        secret_name=c.secret_name,
        sign_name=c.sign_name,
        otp_template_id=c.otp_template_id,
        has_secret_key=bool(c.secret_key_enc),
        is_active=c.is_active,
        last_failure_at=c.last_failure_at,
        last_failure_reason=c.last_failure_reason,
        updated_at=c.updated_at,
    )


@router.get("/sms-config", response_model=SmsConfigOut | None)
async def get_sms_config(
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SmsConfigOut | None:
    c = db.execute(
        select(SmsConfig).order_by(desc(SmsConfig.updated_at)).limit(1)
    ).scalar_one_or_none()
    return _sms_config_to_out(c) if c else None


@router.put("/sms-config", response_model=SmsConfigOut)
async def put_sms_config(
    body: SmsConfigIn,
    _user: Annotated[UserAccount, Depends(require_roles(*SUPER_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SmsConfigOut:
    c = db.execute(
        select(SmsConfig).order_by(desc(SmsConfig.updated_at)).limit(1)
    ).scalar_one_or_none()
    if c is None:
        c = SmsConfig(
            secret_name=body.secret_name,
            secret_key_enc=encrypt_phone(body.secret_key) if body.secret_key else None,
            sign_name=body.sign_name,
            otp_template_id=body.otp_template_id,
            is_active=body.is_active,
        )
        db.add(c)
    else:
        c.secret_name = body.secret_name
        if body.secret_key is not None:
            c.secret_key_enc = encrypt_phone(body.secret_key) if body.secret_key else None
        c.sign_name = body.sign_name
        c.otp_template_id = body.otp_template_id
        c.is_active = body.is_active
    db.commit()
    db.refresh(c)
    return _sms_config_to_out(c)
```

> `encrypt_phone` / `desc` / `select` / `Annotated` / `Depends` / `require_roles` / `get_db` / `Session` / `UserAccount` 在 `super_config.py` 顶部均已 import（blockchain-config 用了同款）。确认无需新增。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_super_config.py -q`
Expected: PASS（既有 + 4 个新 SMS 测试全绿）。

- [ ] **Step 6: ruff + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/schemas/platform.py app/api/super_config.py tests/api/test_super_config.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/platform.py poc/backend/app/api/super_config.py poc/backend/tests/api/test_super_config.py
git commit -m "feat(sms): 超管 GET/PUT /super/sms-config 端点"
```

---

## Task 3: SMS 客户端 `sms_center.py` + `sms_backend` 配置

**Files:**
- Modify: `poc/backend/app/core/config.py`
- Create: `poc/backend/app/services/sms_center.py`
- Test: `poc/backend/tests/services/test_sms_center.py`

- [ ] **Step 1: 写失败测试** — 创建 `poc/backend/tests/services/test_sms_center.py`：

```python
"""短信通道 Task 3 — sms_center.send_otp_sms 测试。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.crypto import encrypt_phone
from app.models.platform import SmsConfig
from app.services import sms_center
from app.services.sms_center import SmsResult, send_otp_sms


def test_mock_backend_returns_ok_without_http(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "mock")
    result = send_otp_sms(db_session, phone="13800001234", code="123456")
    assert result.ok is True
    assert result.batch_id == "mock-otp"


def test_sms_center_no_config_returns_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "sms_center")
    result = send_otp_sms(db_session, phone="13800001234", code="123456")
    assert result.ok is False
    assert result.error == "ERR_SMS_NOT_CONFIGURED"


def test_sms_center_template_mode_success(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "sms_center")
    db_session.add(SmsConfig(
        secret_name="API", secret_key_enc=encrypt_phone("k"),
        sign_name="有证慧催", otp_template_id="T1001", is_active=True,
    ))
    db_session.flush()
    captured = {}

    def fake_call(body: dict) -> dict:
        captured.update(body)
        return {"code": 0, "msg": None, "data": "batch-999"}

    monkeypatch.setattr(sms_center, "_call_sms_center", fake_call)
    result = send_otp_sms(db_session, phone="13800001234", code="123456", ttl_minutes=5)
    assert result.ok is True
    assert result.batch_id == "batch-999"
    assert captured["TemplateId"] == "T1001"
    assert captured["TemplateVars"] == ["123456", "5"]
    assert captured["SignName"] == "【有证慧催】"


def test_sms_center_direct_text_mode_when_no_template(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "sms_center")
    db_session.add(SmsConfig(
        secret_name="API", secret_key_enc=encrypt_phone("k"),
        sign_name="有证慧催", otp_template_id=None, is_active=True,
    ))
    db_session.flush()
    captured = {}

    def fake_call(body: dict) -> dict:
        captured.update(body)
        return {"code": 0, "msg": None, "data": "b1"}

    monkeypatch.setattr(sms_center, "_call_sms_center", fake_call)
    result = send_otp_sms(db_session, phone="13800001234", code="654321")
    assert result.ok is True
    assert "654321" in captured["Content"]
    assert captured.get("TemplateId", "") == ""


def test_sms_center_failure_records_last_failure(db_session, monkeypatch):
    monkeypatch.setattr(settings, "sms_backend", "sms_center")
    cfg = SmsConfig(
        secret_name="API", secret_key_enc=encrypt_phone("k"),
        sign_name="S", otp_template_id="T1", is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()

    def fake_call(body: dict) -> dict:
        return {"code": 1001, "msg": "余额不足", "data": None}

    monkeypatch.setattr(sms_center, "_call_sms_center", fake_call)
    result = send_otp_sms(db_session, phone="13800001234", code="111111")
    assert result.ok is False
    assert result.error == "ERR_SMS_SEND_FAILED"
    db_session.refresh(cfg)
    assert cfg.last_failure_at is not None
    assert "余额不足" in cfg.last_failure_reason
```

> `tests/services/` 目录已存在（`test_streaming_asr_mock.py` 在内）。`db_session` 是 conftest 既有 fixture。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_sms_center.py -q`
Expected: FAIL —— `cannot import ... sms_center`。

- [ ] **Step 3: 加 `sms_backend` 配置** — `poc/backend/app/core/config.py`，在 `mipush_backend` 字段附近追加一行：

```python
    # ==== 短信通道：mock / sms_center（短信中心 028lk）====
    sms_backend: str = "mock"  # "mock" | "sms_center"
```

- [ ] **Step 4: 创建客户端** — `poc/backend/app/services/sms_center.py`：

```python
"""短信中心（028lk）OTP 验证码短信客户端。

settings.sms_backend:
  - "mock"        dev / 测试默认：只打 log，不发真实 HTTP。
  - "sms_center"  读 SmsConfig，真实 POST https://api.028lk.com/Sms/Api/Send。

公开入口仅 send_otp_sms()，永不抛异常，统一返回 SmsResult。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt_phone
from app.models.platform import SmsConfig

logger = logging.getLogger(__name__)

_ENDPOINT = "https://api.028lk.com/Sms/Api/Send"
_HTTP_TIMEOUT = 10.0


@dataclass(frozen=True)
class SmsResult:
    ok: bool
    batch_id: str | None = None
    error: str | None = None


def _mask_phone(phone: str) -> str:
    return phone[:3] + "****" + phone[-4:] if len(phone) >= 11 else "***"


def _call_sms_center(body: dict) -> dict:
    """真实 HTTP POST 到短信中心，返回解析后的 JSON。失败抛异常。

    测试通过 monkeypatch 替换本函数以模拟 028lk 响应。
    """
    with httpx.Client(timeout=_HTTP_TIMEOUT) as cli:
        resp = cli.post(_ENDPOINT, json=body)
    resp.raise_for_status()
    return resp.json()


def _record_failure(db: Session, config: SmsConfig, reason: str) -> None:
    config.last_failure_at = datetime.now(UTC)
    config.last_failure_reason = reason[:500]
    db.commit()


def send_otp_sms(
    db: Session, *, phone: str, code: str, ttl_minutes: int = 5
) -> SmsResult:
    """发送 OTP 验证码短信。永不抛异常 —— 统一返回 SmsResult。"""
    if settings.sms_backend == "mock":
        logger.info(
            "[SMS-mock] OTP → %s code=%s ttl=%dmin", _mask_phone(phone), code, ttl_minutes
        )
        return SmsResult(ok=True, batch_id="mock-otp")

    config = db.execute(
        select(SmsConfig).order_by(desc(SmsConfig.updated_at)).limit(1)
    ).scalar_one_or_none()
    if config is None or not config.is_active or not config.secret_key_enc:
        return SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")

    try:
        secret_key = decrypt_phone(config.secret_key_enc)
    except Exception:
        logger.exception("SmsConfig.secret_key_enc 解密失败")
        return SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")

    sign = config.sign_name or ""
    if sign and not sign.startswith("【"):
        sign = f"【{sign}】"

    body: dict = {
        "SecretName": config.secret_name,
        "SecretKey": secret_key,
        "Mobile": phone,
        "SignName": sign,
    }
    if config.otp_template_id:
        body["TemplateId"] = config.otp_template_id
        body["TemplateVars"] = [code, str(ttl_minutes)]
        body["Content"] = ""
    else:
        body["TemplateId"] = ""
        body["Content"] = f"您的验证码是 {code}，{ttl_minutes} 分钟内有效，请勿泄露。"

    try:
        data = _call_sms_center(body)
    except Exception as exc:  # noqa: BLE001 — 外部 HTTP 任何异常都不应冒泡
        logger.warning("短信中心 HTTP 调用失败: %s", exc)
        _record_failure(db, config, f"HTTP 异常: {exc}")
        return SmsResult(ok=False, error="ERR_SMS_SEND_FAILED")

    if data.get("code") == 0:
        return SmsResult(ok=True, batch_id=str(data.get("data") or ""))

    reason = str(data.get("msg") or f"code={data.get('code')}")
    _record_failure(db, config, reason)
    return SmsResult(ok=False, error="ERR_SMS_SEND_FAILED")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_sms_center.py -q`
Expected: PASS（5 passed）。

- [ ] **Step 6: ruff + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/core/config.py app/services/sms_center.py tests/services/test_sms_center.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/core/config.py poc/backend/app/services/sms_center.py poc/backend/tests/services/test_sms_center.py
git commit -m "feat(sms): sms_center 客户端 send_otp_sms（mock + 028lk 双模式）"
```

---

## Task 4: OTP 端点接线

**Files:**
- Modify: `poc/backend/app/api/auth_extras.py`（`otp_send` ~416、`password_reset_request` ~448）
- Test: `poc/backend/tests/api/test_otp_sms_wiring.py`

- [ ] **Step 1: 写失败测试** — 创建 `poc/backend/tests/api/test_otp_sms_wiring.py`。先 Read 既有 OTP 测试（`grep -rln "otp/send\|otp_send" tests/`）确认 `client` fixture 与造用户/手机号的风格，照搬。测试内容：

```python
"""短信通道 Task 4 — OTP 端点接线测试。"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import sms_center


@pytest.mark.asyncio
async def test_otp_send_calls_sms_in_mock_mode(client, monkeypatch):
    """mock 模式：otp/send 正常返回，dev_code 仍下发，send_otp_sms 被调用。"""
    monkeypatch.setattr(settings, "sms_backend", "mock")
    calls = []
    real = sms_center.send_otp_sms

    def spy(db, *, phone, code, ttl_minutes=5):
        calls.append(phone)
        return real(db, phone=phone, code=code, ttl_minutes=ttl_minutes)

    monkeypatch.setattr("app.api.auth_extras.send_otp_sms", spy)
    r = await client.post("/api/v1/auth/otp/send", json={"phone": "13800009999", "purpose": "login"})
    assert r.status_code == 200
    assert r.json()["sent"] is True
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_otp_send_returns_sms_failed_when_send_fails(client, monkeypatch):
    """真实 backend 下 send_otp_sms 失败 → 403 ERR_SMS_SEND_FAILED。"""
    monkeypatch.setattr(settings, "sms_backend", "sms_center")

    def fail(db, *, phone, code, ttl_minutes=5):
        return sms_center.SmsResult(ok=False, error="ERR_SMS_NOT_CONFIGURED")

    monkeypatch.setattr("app.api.auth_extras.send_otp_sms", fail)
    r = await client.post("/api/v1/auth/otp/send", json={"phone": "13800008888", "purpose": "login"})
    assert r.status_code == 403
    assert r.json()["code"] == "ERR_SMS_SEND_FAILED"
```

> 若既有 OTP 测试用别的 client fixture 名 / 需预置用户，按既有风格对齐。`password_reset_request` 因「用户不存在仍假装成功」，需造一个真实用户才能测其发短信路径 —— 可选补一条，但上面两条已覆盖核心接线。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_otp_sms_wiring.py -q`
Expected: FAIL —— `otp_send` 未调 `send_otp_sms`（`calls` 为空 / 不返回 403）。

- [ ] **Step 3: 改 `auth_extras.py`** — import 区追加 `from app.core.config import settings` 与 `from app.services.sms_center import send_otp_sms`。

把 `otp_send` 整体替换为：

```python
@router.post("/otp/send", response_model=OtpSendOut)
def otp_send(body: OtpSendIn, db: Session = Depends(get_db)) -> OtpSendOut:
    code = _create_otp(db, body.phone, body.purpose)
    result = send_otp_sms(db, phone=body.phone, code=code, ttl_minutes=OTP_TTL_SECONDS // 60)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_SMS_SEND_FAILED", "message": "验证码短信发送失败，请稍后重试"},
        )
    return OtpSendOut(
        sent=True,
        expires_in=OTP_TTL_SECONDS,
        dev_code=code if OTP_DEV_RETURN else None,
    )
```

把 `password_reset_request` 的 `if user:` 分支整体替换为：

```python
    # 用户不存在仍假装成功（防爆破探测）
    if user:
        code = _create_otp(db, body.phone, "password_reset")
        result = send_otp_sms(db, phone=body.phone, code=code, ttl_minutes=OTP_TTL_SECONDS // 60)
        if not result.ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ERR_SMS_SEND_FAILED", "message": "验证码短信发送失败，请稍后重试"},
            )
        return OtpSendOut(
            sent=True,
            expires_in=OTP_TTL_SECONDS,
            dev_code=code if OTP_DEV_RETURN else None,
        )
    return OtpSendOut(sent=True, expires_in=OTP_TTL_SECONDS)
```

> `mock` 模式 `result.ok` 恒为 True，`if not result.ok` 分支不会触发，dev 联调不受影响。

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_otp_sms_wiring.py -q && python3.12 -m pytest tests/ -q -k "otp"`
Expected: 新测试 PASS；既有 OTP 测试无回归（既有测试默认 `sms_backend="mock"`，`send_otp_sms` 恒成功，不破坏既有断言）。

- [ ] **Step 5: ruff + commit**

```bash
cd poc/backend && python3.12 -m ruff check app/api/auth_extras.py tests/api/test_otp_sms_wiring.py
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/api/auth_extras.py poc/backend/tests/api/test_otp_sms_wiring.py
git commit -m "feat(sms): otp_send / password_reset_request 接入短信发送"
```

---

## Task 5: 前端超管短信配置页

**Files:**
- Create: `frontend/src/pages/super/sms-config/index.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/config/nav.ts`
- Modify: `frontend/src/config/__tests__/nav.test.ts`

- [ ] **Step 1: 写失败测试** — 在 `frontend/src/config/__tests__/nav.test.ts` 增加（先 Read 该文件确认 superadmin nav 测试组写法）：

```ts
it("superadmin nav 含短信配置", () => {
  const paths = getNavSections("superadmin")
    .flatMap((s) => s.items)
    .map((i) => i.path);
  expect(paths).toContain("/super/sms-config");
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend && npx vitest run src/config/__tests__/nav.test.ts`
Expected: FAIL —— 新用例 `toContain("/super/sms-config")` 失败。

- [ ] **Step 3: 创建配置页** — 创建 `frontend/src/pages/super/sms-config/index.tsx`。该页是 `frontend/src/pages/super/blockchain-config/index.tsx` 的同构镜像 —— 先 Read 那个文件，按下面差异改写（去掉 provider 下拉、字段换成短信配置字段）：

```tsx
// 短信通道 — 平台超管短信中心（028lk）配置
import { useCustom, useCustomMutation } from "@refinedev/core";
import { MessageSquare, Save, AlertTriangle, CheckCircle2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface SmsConfig {
  id: number;
  secret_name: string;
  sign_name: string;
  otp_template_id: string | null;
  has_secret_key: boolean;
  is_active: boolean;
  last_failure_at: string | null;
  last_failure_reason: string | null;
  updated_at: string;
}

export function SuperSmsConfigPage() {
  const { query } = useCustom<SmsConfig>({
    url: "super/sms-config",
    method: "get",
  });
  const config = query.data?.data ?? null;

  const [secretName, setSecretName] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [signName, setSignName] = useState("");
  const [otpTemplateId, setOtpTemplateId] = useState("");
  const [isActive, setIsActive] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState("");

  const initRef = useRef(false);
  useEffect(() => {
    if (config && !initRef.current) {
      initRef.current = true;
      setSecretName(config.secret_name);
      setSignName(config.sign_name);
      setOtpTemplateId(config.otp_template_id ?? "");
      setIsActive(config.is_active);
    }
  }, [config]);

  const { mutate: save, mutation } = useCustomMutation();

  const submit = () => {
    setError("");
    if (!secretName) {
      setError("短信中心账户名不能为空");
      return;
    }
    save(
      {
        url: "super/sms-config",
        method: "put",
        values: {
          secret_name: secretName,
          secret_key: secretKey || null,
          sign_name: signName,
          otp_template_id: otpTemplateId || null,
          is_active: isActive,
        },
      },
      {
        onSuccess: () => {
          setSavedAt(new Date().toLocaleTimeString("zh-CN"));
          setSecretKey("");
          query.refetch();
        },
        onError: () => setError("保存失败"),
      },
    );
  };

  if (query.isLoading) {
    return <div className="p-6 text-[var(--color-neutral-400)]">加载中…</div>;
  }

  return (
    <div className="p-6 max-w-2xl space-y-4">
      <div className="flex items-center gap-2">
        <MessageSquare className="w-5 h-5 text-[var(--color-primary)]" />
        <h1 className="text-xl font-semibold">短信配置</h1>
      </div>

      {!config ? (
        <div
          className="p-4 bg-[var(--color-warning-light)] text-sm flex items-center gap-2"
          style={{ borderRadius: "var(--radius-md)", color: "var(--color-warning)" }}
        >
          <AlertTriangle className="w-4 h-4" />
          尚未配置短信中心。配置并激活后，登录 / 密码重置验证码方可经短信送达。
        </div>
      ) : config.is_active ? (
        <div
          className="p-4 bg-[var(--color-success-light)] text-sm flex items-center gap-2"
          style={{ borderRadius: "var(--radius-md)", color: "var(--color-success)" }}
        >
          <CheckCircle2 className="w-4 h-4" />
          短信通道已激活
        </div>
      ) : null}

      {config?.last_failure_at && (
        <div
          className="p-3 bg-[var(--color-danger-light)] text-sm"
          style={{ borderRadius: "var(--radius-md)", color: "var(--color-danger)" }}
        >
          最近失败：{config.last_failure_at?.slice(0, 19).replace("T", " ")} ·
          {config.last_failure_reason}
        </div>
      )}

      <div
        className="bg-white p-5 border border-[var(--color-neutral-200)] space-y-4"
        style={{ borderRadius: "var(--radius-lg)" }}
      >
        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            短信中心账户名（SecretName）
          </label>
          <input
            type="text"
            value={secretName}
            onChange={(e) => setSecretName(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            密钥（SecretKey）
          </label>
          <input
            type="password"
            value={secretKey}
            onChange={(e) => setSecretKey(e.target.value)}
            placeholder={
              config?.has_secret_key ? "••••••（已配置，留空保持不变）" : "请输入密钥"
            }
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
          <p className="text-xs text-[var(--color-neutral-400)] mt-1">
            提交后服务端 AES-256 加密落库；查询接口仅返回是否已配置
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            短信签名
          </label>
          <input
            type="text"
            value={signName}
            onChange={(e) => setSignName(e.target.value)}
            placeholder="如：有证慧催"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            OTP 验证码模板 ID
          </label>
          <input
            type="text"
            value={otpTemplateId}
            onChange={(e) => setOtpTemplateId(e.target.value)}
            placeholder="留空则用直接文本模式发送"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>

        <div>
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="w-4 h-4"
            />
            激活短信通道
          </label>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex items-center justify-between">
          {savedAt ? (
            <span className="text-xs text-[var(--color-success)]">已保存 ({savedAt})</span>
          ) : (
            <span />
          )}
          <button
            type="button"
            onClick={submit}
            disabled={mutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            style={{ background: "var(--color-primary)", borderRadius: "var(--radius-md)" }}
          >
            <Save className="w-4 h-4" />
            {mutation.isPending ? "保存中…" : "保存配置"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 注册路由** — `frontend/src/App.tsx`。仿照 `SuperBlockchainConfigPage` 的 import（约 79 行）加：

```tsx
import { SuperSmsConfigPage } from "./pages/super/sms-config";
```

仿照 `/super/blockchain-config` 的 `<Route>`（约 507 行）加：

```tsx
            <Route path="/super/sms-config" element={<SuperSmsConfigPage />} />
```

- [ ] **Step 5: 加 nav** — `frontend/src/config/nav.ts`，`NAV_CONFIG.superadmin` 的「系统管理」区，在「区块链配置」项后加：

```ts
        { label: "短信配置", path: "/super/sms-config", icon: "MessageSquare" },
```

- [ ] **Step 6: 跑测试 + typecheck + lint**

```bash
cd frontend
npx vitest run src/config/__tests__/nav.test.ts
npx tsc -p tsconfig.json --noEmit
npx eslint src/config/nav.ts src/config/__tests__/nav.test.ts src/pages/super/sms-config/index.tsx src/App.tsx
```
Expected: vitest PASS；tsc 退出码 0；eslint 退出码 0。

- [ ] **Step 7: commit**

```bash
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/super/sms-config/index.tsx frontend/src/App.tsx frontend/src/config/nav.ts frontend/src/config/__tests__/nav.test.ts
git commit -m "feat(sms): 超管短信配置页 /super/sms-config"
```

---

## Task 6: 全量回归 + 标注 spec

**Files:**
- Modify: `docs/superpowers/specs/2026-05-18-sms-otp-channel-design.md`

- [ ] **Step 1: 后端全量回归**

Run: `cd poc/backend && python3.12 -m pytest -q`
Expected: 全绿（既有 865 passed + 本计划新增 ~13 个测试）。失败先修再继续。

- [ ] **Step 2: 前端回归 + typecheck**

Run: `cd frontend && npx vitest run && npx tsc -p tsconfig.json --noEmit`
Expected: vitest 全绿；tsc 退出码 0。

- [ ] **Step 3: 标注 spec** — 在 `docs/superpowers/specs/2026-05-18-sms-otp-channel-design.md` 末尾「风险」节后追加：

```markdown

---

> ✅ **已实现（2026-05-18）**：`SmsConfig` 平台级配置表 + 超管 `GET/PUT /super/sms-config` + `sms_center.py` 客户端（mock / 028lk 双模式）+ OTP 端点（`otp_send` / `password_reset_request`）接入短信发送 + 超管前端配置页。每环节配测试。
```

- [ ] **Step 4: commit**

```bash
cd /Users/shuo/AI/autoluyin
git add docs/superpowers/specs/2026-05-18-sms-otp-channel-design.md
git commit -m "docs(sms): 标注短信通道实现完成"
```

---

## Self-Review

**1. Spec 覆盖**：
- 设计「① `SmsConfig`」→ Task 1（模型 + 迁移）。✓
- 「② 超管 API」→ Task 2（schema + GET/PUT 端点）。✓
- 「③ SMS 客户端 `sms_center.py`」→ Task 3（`send_otp_sms` + `sms_backend` 配置 + 双模式 + 失败记录）。✓
- 「④ OTP 链路接线」→ Task 4（`otp_send` / `password_reset_request` + `ERR_SMS_SEND_FAILED`）。✓
- 「⑤ 前端」→ Task 5（配置页 + 路由 + nav）。✓
- 「测试」→ 各 Task 内置 TDD + Task 6 全量回归。✓
- 「错误处理」`ERR_SMS_SEND_FAILED` / `ERR_SMS_NOT_CONFIGURED` → Task 3/4 实现并测试。✓
- 「不在范围」通知渠道 stub / 支付链接 / 邮箱 OTP / 计费 → 计划均未触碰。✓

**2. 占位符扫描**：Task 2 Step 1 的 `agent_auth_headers` 与 Task 4 Step 1 的 client fixture 标注了「按测试文件既有 fixture 对齐」—— 这是对既有测试基建真实命名的必要核对指令，非占位（每个测试文件的非超管 fixture 命名需现场确认）。其余步骤均为完整代码 + 确切命令 + 预期输出。

**3. 类型/命名一致性**：`SmsConfig`（模型，Task 1）→ `SmsConfigIn`/`SmsConfigOut`（schema，Task 2）→ `sms_center.send_otp_sms` 消费 `SmsConfig`（Task 3）→ `auth_extras` 调 `send_otp_sms`（Task 4）一致引用。`SmsResult(ok, batch_id, error)` 在 Task 3 定义、Task 4 消费 `.ok`。迁移 revision `24020v220f` ← `24019v220e`。`secret_key_enc` 用 `encrypt_phone` 加密（Task 2）/ `decrypt_phone` 解密（Task 3）成对。错误码 `ERR_SMS_NOT_CONFIGURED`（Task 3）、`ERR_SMS_SEND_FAILED`（Task 3 返回 / Task 4 转 403）一致。
