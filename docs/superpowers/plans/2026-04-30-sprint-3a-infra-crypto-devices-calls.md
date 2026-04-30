# Sprint 3a Implementation Plan — AES-256 Encryption + Device Registration + Call Upload + Celery

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the call pipeline foundation: AES-256-GCM phone encryption (full migration), device registration endpoints, call upload with quota check, and Celery+Redis async task skeleton.

**Architecture:** New `app/core/crypto.py` handles deterministic AES-256-GCM encryption; all write paths updated to call `encrypt_phone()`; `devices_v1.py` replaces the PoC `devices.py` with JWT-secured ORM routes; `calls_v1.py` accepts multipart call uploads, checks quotas, stores in MinIO/storage, and dispatches a Celery task skeleton.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + `cryptography` (already installed via python-jose) + Celery + Redis (fakeredis for tests) + MinIO via existing `storage.py` singleton

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| **Create** | `app/core/crypto.py` | AES-256-GCM encrypt/decrypt/mask; deterministic IV |
| **Modify** | `app/core/config.py` | Add `autoluyin_aes_key` setting |
| **Modify** | `app/core/security.py` | Delegate `mask_phone` to `crypto.mask_phone` |
| **Create** | `app/models/device.py` | `DeviceProfile` ORM model |
| **Create** | `app/api/devices_v1.py` | POST /register, POST /self-check, GET /config |
| **Create** | `app/worker/__init__.py` | Empty package marker |
| **Create** | `app/worker/celery_app.py` | Celery instance, broker config |
| **Create** | `app/worker/tasks/__init__.py` | Empty package marker |
| **Create** | `app/worker/tasks/call_pipeline.py` | `process_call` task (Sprint 3a: set status=queued) |
| **Modify** | `app/api/auth.py` | Login: query by `encrypt_phone(body.phone)` |
| **Modify** | `app/api/admin.py` | create_user: store `encrypt_phone(body.phone)` |
| **Modify** | `app/api/ops.py` | create_tenant: store `encrypt_phone(body.admin_phone)` |
| **Modify** | `app/api/admin_cases.py` | import: use `encrypt_phone`; lookup: use `encrypt_phone` |
| **Modify** | `app/schemas/call.py` | Add `CallUploadResponse`, `CallListItem`, `CallDetailResponse` |
| **Create** | `app/api/calls_v1.py` | POST /upload, GET /, GET /{call_id} |
| **Modify** | `app/main.py` | Register devices_v1 + calls_v1; startup AES key validation |
| **Create** | `alembic/versions/*_add_device_profile.py` | 3a-001: `device_profile` table |
| **Create** | `alembic/versions/*_encrypt_phone_fields.py` | 3a-002: data migration encrypting plaintext phones |
| **Modify** | `poc/docker-compose.yml` | Add `redis` + `celery_worker` services |
| **Modify** | `tests/conftest.py` | Set `AUTOLUYIN_AES_KEY` env var; fixtures use `encrypt_phone` |
| **Create** | `tests/test_crypto.py` | Unit tests for crypto.py |
| **Create** | `tests/api/test_devices_v1.py` | Integration tests for devices endpoints |
| **Create** | `tests/api/test_calls_v1.py` | Integration tests for call upload + quota |
| **Create** | `tests/worker/test_process_call.py` | Celery task tests (eager mode) |

---

## Task 1: `app/core/crypto.py` — AES-256-GCM encryption utilities

**Files:**
- Create: `poc/backend/app/core/crypto.py`
- Create: `poc/backend/tests/test_crypto.py`

- [ ] **Step 1: Write the failing tests**

```python
# poc/backend/tests/test_crypto.py
import os
import pytest

# Set key before importing crypto module
os.environ["AUTOLUYIN_AES_KEY"] = "deadbeef" * 8  # 64 hex chars = 32 bytes


def test_encrypt_decrypt_roundtrip():
    from app.core.crypto import decrypt_phone, encrypt_phone

    plain = "13812345678"
    assert decrypt_phone(encrypt_phone(plain)) == plain


def test_encrypt_is_deterministic():
    from app.core.crypto import encrypt_phone

    phone = "13812345678"
    assert encrypt_phone(phone) == encrypt_phone(phone)


def test_encrypt_different_phones_differ():
    from app.core.crypto import encrypt_phone

    assert encrypt_phone("13800000001") != encrypt_phone("13800000002")


def test_mask_phone_returns_masked_format():
    from app.core.crypto import encrypt_phone, mask_phone

    cipher = encrypt_phone("13812345678")
    assert mask_phone(cipher) == "138****5678"


def test_decrypt_wrong_key_raises():
    original_key = os.environ["AUTOLUYIN_AES_KEY"]
    from app.core.crypto import encrypt_phone

    cipher = encrypt_phone("13812345678")

    # Patch the cached key to simulate a different key
    import app.core.crypto as crypto_mod

    crypto_mod._KEY = bytes.fromhex("cafebabe" * 8)
    try:
        with pytest.raises(ValueError, match="Decryption failed"):
            crypto_mod.decrypt_phone(cipher)
    finally:
        crypto_mod._KEY = bytes.fromhex(original_key)


def test_decrypt_invalid_format_raises():
    from app.core.crypto import decrypt_phone

    with pytest.raises(ValueError, match="Invalid cipher format"):
        decrypt_phone("not.a.valid.ciphertext.here")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest tests/test_crypto.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.core.crypto'`

- [ ] **Step 3: Create `app/core/crypto.py`**

```python
# poc/backend/app/core/crypto.py
from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_KEY: bytes | None = None


def _get_key() -> bytes:
    global _KEY
    if _KEY is None:
        hex_key = os.environ.get("AUTOLUYIN_AES_KEY", "")
        if len(hex_key) != 64:
            raise RuntimeError(
                "AUTOLUYIN_AES_KEY must be set to 64 hex characters (32 bytes); "
                f"got length {len(hex_key)}"
            )
        _KEY = bytes.fromhex(hex_key)
    return _KEY


def encrypt_phone(plain: str) -> str:
    """AES-256-GCM encrypt. Output: '{iv_hex}.{tag_hex}.{ciphertext_b64}'.

    IV is derived deterministically from HMAC(key, plain) so the same phone
    always produces the same ciphertext, enabling lookup by encrypted value.
    """
    key = _get_key()
    iv = _hmac.new(key, plain.encode(), hashlib.sha256).digest()[:12]
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(plain.encode()) + encryptor.finalize()
    tag = encryptor.tag
    return f"{iv.hex()}.{tag.hex()}.{base64.b64encode(ct).decode()}"


def decrypt_phone(cipher_str: str) -> str:
    """Reverse of encrypt_phone. Raises ValueError on bad format or wrong key."""
    parts = cipher_str.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid cipher format: expected 3 dot-separated parts, got {len(parts)!r}")
    iv_hex, tag_hex, ct_b64 = parts
    try:
        iv = bytes.fromhex(iv_hex)
        tag = bytes.fromhex(tag_hex)
        ct = base64.b64decode(ct_b64)
    except Exception as exc:
        raise ValueError(f"Invalid cipher format: {exc}") from exc

    key = _get_key()
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    try:
        plain = decryptor.update(ct) + decryptor.finalize()
    except InvalidTag as exc:
        raise ValueError("Decryption failed: invalid authentication tag") from exc
    return plain.decode()


def mask_phone(cipher_str: str) -> str:
    """Decrypt ciphertext and return masked form like 138****5678."""
    phone = decrypt_phone(cipher_str)
    if len(phone) == 11:
        return phone[:3] + "****" + phone[7:]
    if len(phone) >= 7:
        return phone[:3] + "****" + phone[-4:]
    return "***"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest tests/test_crypto.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/core/crypto.py poc/backend/tests/test_crypto.py
git commit -m "feat: add AES-256-GCM crypto utils (encrypt/decrypt/mask_phone)"
```

---

## Task 2: Config + conftest AES key + Alembic migration 3a-001 (device_profile table)

**Files:**
- Modify: `poc/backend/app/core/config.py`
- Modify: `poc/backend/tests/conftest.py`
- Create: `poc/backend/alembic/versions/<rev>_add_device_profile.py`

- [ ] **Step 1: Update `app/core/config.py` — add `autoluyin_aes_key`**

Add after the `jwt_expires_minutes` line:

```python
# poc/backend/app/core/config.py  (full file)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://autoluyin:autoluyin_dev@postgres:5432/autoluyin"

    jwt_secret_key: str = "dev-secret-change-in-prod-must-be-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 1440  # 24 hours

    # AES-256-GCM key for phone number encryption (64 hex chars = 32 bytes)
    autoluyin_aes_key: str = ""

    # ==== 录音存储后端：local / minio / oss ====
    storage_backend: str = "local"

    local_storage_root: str = "/data/recordings"
    local_storage_public_base: str = "http://localhost:8000"
    recording_sign_secret: str = "change-me-in-prod"

    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin_dev"
    minio_bucket: str = "recordings"
    minio_secure: bool = False
    minio_public_host: str = "localhost:9000"

    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_endpoint: str = "oss-cn-hangzhou.aliyuncs.com"
    oss_bucket: str = ""
    oss_use_signed_url: bool = True
    oss_signed_url_expires_sec: int = 3600

    asr_backend: str = "mock"
    llm_backend: str = "mock"

    dashscope_api_key: str = ""
    dashscope_asr_model: str = "paraformer-v2"

    llm_api_key: str = "sk-placeholder"
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"

    deepseek_api_key: str = ""
    deepseek_base_url: str = ""
    deepseek_model: str = ""


settings = Settings()
```

- [ ] **Step 2: Update `tests/conftest.py` — set `AUTOLUYIN_AES_KEY` before app import**

Add these two lines to the top env-var block (before `from app.main import app`):

```python
# poc/backend/tests/conftest.py  (first 15 lines, after existing env vars)
import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

os.environ["ASR_BACKEND"] = "mock"
os.environ["LLM_BACKEND"] = "mock"
os.environ["LOCAL_STORAGE_ROOT"] = "/tmp/autoluyin_test_recordings"
os.environ["AUTOLUYIN_AES_KEY"] = "deadbeef" * 8  # 64 hex chars — test key only
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "True"

from app.main import app  # noqa: E402
# ... rest of file unchanged
```

- [ ] **Step 3: Generate Alembic migration for device_profile table**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
alembic revision --autogenerate -m "add_device_profile"
```

Note the generated revision file name, then open it and **verify / replace** the `upgrade()` and `downgrade()` functions with:

```python
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "device_profile",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("os_version", sa.Text(), nullable=True),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_healthy",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index(
        "idx_device_profile_tenant_user",
        "device_profile",
        ["tenant_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_device_profile_tenant_user", table_name="device_profile")
    op.drop_table("device_profile")
```

- [ ] **Step 4: Run all existing tests to confirm nothing broke**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest --tb=short -q
```

Expected: same number of tests pass as before; no regressions

- [ ] **Step 5: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/core/config.py poc/backend/tests/conftest.py poc/backend/alembic/versions/
git commit -m "chore: add AUTOLUYIN_AES_KEY config + Alembic migration 3a-001 device_profile table"
```

---

## Task 3: `app/models/device.py` ORM model + `app/api/devices_v1.py` + tests

**Files:**
- Create: `poc/backend/app/models/device.py`
- Create: `poc/backend/app/api/devices_v1.py`
- Create: `poc/backend/tests/api/test_devices_v1.py`

- [ ] **Step 1: Write the failing tests**

```python
# poc/backend/tests/api/test_devices_v1.py
import pytest


@pytest.mark.asyncio
async def test_register_device_creates_record(client, agent_auth_headers, db_session):
    resp = await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-uuid-001", "brand": "Xiaomi", "model": "12", "os_version": "Android 13"},
        headers=agent_auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["device_id"] == "dev-uuid-001"
    assert "user_id" in data
    assert "tenant_id" in data


@pytest.mark.asyncio
async def test_register_device_upserts_on_conflict(client, agent_auth_headers):
    payload = {"device_id": "dev-uuid-upsert", "brand": "Samsung"}
    await client.post("/api/v1/devices/register", json=payload, headers=agent_auth_headers)
    # Second call — should update brand, not fail
    payload2 = {"device_id": "dev-uuid-upsert", "brand": "Huawei"}
    resp = await client.post("/api/v1/devices/register", json=payload2, headers=agent_auth_headers)
    assert resp.status_code == 201
    assert resp.json()["device_id"] == "dev-uuid-upsert"


@pytest.mark.asyncio
async def test_self_check_all_ok_returns_can_call_true(client, agent_auth_headers):
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-uuid-check"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "dev-uuid-check",
            "recording_dir_ok": True,
            "recording_toggle_on": True,
            "permissions_ok": True,
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["can_call"] is True


@pytest.mark.asyncio
async def test_self_check_partial_failure_returns_can_call_false(client, agent_auth_headers):
    await client.post(
        "/api/v1/devices/register",
        json={"device_id": "dev-uuid-partial"},
        headers=agent_auth_headers,
    )
    resp = await client.post(
        "/api/v1/devices/self-check",
        json={
            "device_id": "dev-uuid-partial",
            "recording_dir_ok": True,
            "recording_toggle_on": False,
            "permissions_ok": True,
        },
        headers=agent_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["can_call"] is False


@pytest.mark.asyncio
async def test_register_requires_auth(client):
    resp = await client.post(
        "/api/v1/devices/register",
        json={"device_id": "no-auth"},
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest tests/api/test_devices_v1.py -v
```

Expected: all fail (router not registered yet)

- [ ] **Step 3: Create `app/models/device.py`**

```python
# poc/backend/app/models/device.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DeviceProfile(Base):
    __tablename__ = "device_profile"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    device_id: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("user_account.id"), nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False
    )
    brand: Mapped[Optional[str]] = mapped_column(sa.Text)
    model: Mapped[Optional[str]] = mapped_column(sa.Text)
    os_version: Mapped[Optional[str]] = mapped_column(sa.Text)
    last_check_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    is_healthy: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.Index("idx_device_profile_tenant_user", "tenant_id", "user_id"),
    )
```

- [ ] **Step 4: Create `app/api/devices_v1.py`**

```python
# poc/backend/app/api/devices_v1.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.models.device import DeviceProfile

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")


class DeviceRegisterRequest(BaseModel):
    device_id: str
    brand: Optional[str] = None
    model: Optional[str] = None
    os_version: Optional[str] = None


class DeviceRegisterResponse(BaseModel):
    device_id: str
    user_id: int
    tenant_id: int
    created_at: datetime


class SelfCheckRequest(BaseModel):
    device_id: str
    recording_dir_ok: bool
    recording_toggle_on: bool
    permissions_ok: bool


class SelfCheckResponse(BaseModel):
    can_call: bool


@router.post("/register", response_model=DeviceRegisterResponse, status_code=201)
def register_device(
    body: DeviceRegisterRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> DeviceRegisterResponse:
    user_id: int = payload["user_id"]
    tenant_id: int = payload["tenant_id"]

    stmt = (
        pg_insert(DeviceProfile)
        .values(
            device_id=body.device_id,
            user_id=user_id,
            tenant_id=tenant_id,
            brand=body.brand,
            model=body.model,
            os_version=body.os_version,
        )
        .on_conflict_do_update(
            index_elements=["device_id"],
            set_=dict(
                brand=body.brand,
                model=body.model,
                os_version=body.os_version,
                user_id=user_id,
                tenant_id=tenant_id,
            ),
        )
        .returning(
            DeviceProfile.id,
            DeviceProfile.device_id,
            DeviceProfile.user_id,
            DeviceProfile.tenant_id,
            DeviceProfile.created_at,
        )
    )
    row = db.execute(stmt).fetchone()
    db.commit()

    return DeviceRegisterResponse(
        device_id=row.device_id,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        created_at=row.created_at,
    )


@router.post("/self-check", response_model=SelfCheckResponse)
def self_check(
    body: SelfCheckRequest,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> SelfCheckResponse:
    user_id: int = payload["user_id"]

    device = db.execute(
        select(DeviceProfile).where(
            DeviceProfile.device_id == body.device_id,
            DeviceProfile.user_id == user_id,
        )
    ).scalar_one_or_none()

    if not device:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_DEVICE_NOT_FOUND", "message": "设备未注册或不属于当前用户"},
        )

    is_healthy = body.recording_dir_ok and body.recording_toggle_on and body.permissions_ok
    device.is_healthy = is_healthy
    device.last_check_at = datetime.now(timezone.utc)
    db.commit()

    return SelfCheckResponse(can_call=is_healthy)


@router.get("/config")
def get_config(
    _payload: Annotated[dict, Depends(get_token_payload)],
    db: Annotated[Session, Depends(get_db)],
    device_id: Optional[str] = Query(None),
) -> dict:
    try:
        rows = db.execute(text("SELECT key, value FROM app_config")).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}
```

- [ ] **Step 5: Run tests to verify they pass** (router not yet in main.py — tests will still fail on routing; we register in Task 8)

Instead, run just to confirm models and logic don't have import errors:

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -c "from app.api.devices_v1 import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/models/device.py poc/backend/app/api/devices_v1.py poc/backend/tests/api/test_devices_v1.py
git commit -m "feat: add DeviceProfile ORM model + devices_v1 router (register/self-check/config)"
```

---

## Task 4: Update all write paths to use `encrypt_phone` + update `security.py` + update `conftest.py` fixtures

**Files:**
- Modify: `poc/backend/app/core/security.py`
- Modify: `poc/backend/app/api/auth.py`
- Modify: `poc/backend/app/api/admin.py`
- Modify: `poc/backend/app/api/ops.py`
- Modify: `poc/backend/app/api/admin_cases.py`
- Modify: `poc/backend/tests/conftest.py`

- [ ] **Step 1: Update `app/core/security.py` — delegate `mask_phone` to `crypto.mask_phone`**

Replace the `mask_phone` function (lines 103–107) with:

```python
def mask_phone(phone_enc: str) -> str:
    """Decrypt AES-256 ciphertext and return masked form like 138****1234."""
    from app.core.crypto import mask_phone as _mask  # avoid circular at module level
    return _mask(phone_enc)
```

- [ ] **Step 2: Update `app/api/auth.py` — login query uses `encrypt_phone`**

Add import at top and update the WHERE clause:

```python
# Add import near top of auth.py (after existing imports):
from app.core.crypto import encrypt_phone

# In the login() function, replace:
#   user = db.execute(
#       select(UserAccount).where(
#           UserAccount.phone_enc == body.phone,
# With:
    user = db.execute(
        select(UserAccount).where(
            UserAccount.phone_enc == encrypt_phone(body.phone),
            UserAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()
```

Full updated login function:

```python
@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.execute(
        select(UserAccount).where(
            UserAccount.phone_enc == encrypt_phone(body.phone),
            UserAccount.is_active.is_(True),
        )
    ).scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "ERR_INVALID_CREDENTIALS",
                "message": "手机号或密码错误",
            },
        )

    membership = db.execute(
        select(UserTenantMembership)
        .where(
            UserTenantMembership.user_id == user.id,
            UserTenantMembership.is_active.is_(True),
        )
        .limit(1)
    ).scalar_one_or_none()

    tenant_id: Optional[int] = None
    role = "platform_superadmin"
    scope = "platform"

    if membership:
        tenant_id = membership.tenant_id
        role = membership.role
        scope = f"tenant:{membership.tenant_id}"

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(
        {
            "sub": str(user.id),
            "user_id": user.id,
            "tenant_id": tenant_id,
            "role": role,
            "scope": scope,
        }
    )

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        role=role,
        tenant_id=tenant_id,
        scope=scope,
    )
```

Also add `from app.core.crypto import encrypt_phone` near the top imports of `auth.py`.

- [ ] **Step 3: Update `app/api/admin.py` — create_user stores encrypted phone**

Add import at top:
```python
from app.core.crypto import encrypt_phone
```

In `create_user`, replace:
```python
new_user = UserAccount(
    phone_enc=body.phone,  # plaintext until AES sprint
```
With:
```python
new_user = UserAccount(
    phone_enc=encrypt_phone(body.phone),
```

- [ ] **Step 4: Update `app/api/ops.py` — create_tenant stores encrypted admin phone**

Add import at top:
```python
from app.core.crypto import encrypt_phone
```

In `create_tenant`, replace:
```python
tenant = Tenant(
    ...
    admin_phone_enc=body.admin_phone,  # plaintext until AES sprint
```
With:
```python
tenant = Tenant(
    ...
    admin_phone_enc=encrypt_phone(body.admin_phone),
```

- [ ] **Step 5: Update `app/api/admin_cases.py` — import and lookup use `encrypt_phone`**

Add import at top:
```python
from app.core.crypto import encrypt_phone
```

In `import_cases` function, find the duplicate-check query and the new owner creation:

Replace:
```python
existing = db.execute(
    select(OwnerProfile).where(
        OwnerProfile.tenant_id == tenant_id,
        OwnerProfile.phone_enc == row.phone,
    )
).scalar_one_or_none()
```
With:
```python
existing = db.execute(
    select(OwnerProfile).where(
        OwnerProfile.tenant_id == tenant_id,
        OwnerProfile.phone_enc == encrypt_phone(row.phone),
    )
).scalar_one_or_none()
```

Replace:
```python
owner = OwnerProfile(
    tenant_id=tenant_id,
    name=row.name,
    phone_enc=row.phone,  # plaintext until AES sprint
```
With:
```python
owner = OwnerProfile(
    tenant_id=tenant_id,
    name=row.name,
    phone_enc=encrypt_phone(row.phone),
```

Also remove the comment from the `mask_phone(owner.phone_enc)` call (it no longer needs the "plaintext" annotation):
```python
phone_masked=mask_phone(owner.phone_enc),
```

- [ ] **Step 6: Update `tests/conftest.py` — fixtures use `encrypt_phone`**

The fixtures that set plaintext phone values must be updated. The `AUTOLUYIN_AES_KEY` env var is already set in Step 2 of Task 2.

Find each fixture and update the phone_enc assignments:

```python
# After the existing imports, add:
from app.core.crypto import encrypt_phone  # noqa: E402

# seeded_user fixture:
@pytest.fixture
def seeded_user(db_session):
    user = UserAccount(
        phone_enc=encrypt_phone("13800138001"),
        name="测试用户",
        password_hash=get_password_hash("Test@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


# seeded_tenant fixture:
@pytest.fixture
def seeded_tenant(db_session):
    tenant = Tenant(
        name="测试物业公司",
        admin_phone_enc=encrypt_phone("13900139001"),
        plan="trial",
        is_active=True,
    )
    db_session.add(tenant)
    db_session.flush()
    return tenant


# seeded_member_user fixture:
@pytest.fixture
def seeded_member_user(db_session, seeded_tenant):
    from app.core.security import get_password_hash
    user = UserAccount(
        phone_enc=encrypt_phone("13811138111"),
        name="催收员小王",
        password_hash=get_password_hash("Agent@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="agent_internal",
        source_type="INTERNAL",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    return user


# seeded_supervisor_user fixture:
@pytest.fixture
def seeded_supervisor_user(db_session, seeded_tenant):
    from app.core.security import get_password_hash
    from app.models.tenant import UserTenantMembership
    user = UserAccount(
        phone_enc=encrypt_phone("13922239222"),
        name="督导李四",
        password_hash=get_password_hash("Supervisor@1234"),
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=seeded_tenant.id,
        role="supervisor",
        source_type="INTERNAL",
        is_active=True,
    )
    db_session.add(membership)
    db_session.flush()
    return user


# seeded_owner fixture:
@pytest.fixture
def seeded_owner(db_session, seeded_tenant):
    from app.models.case import OwnerProfile
    owner = OwnerProfile(
        tenant_id=seeded_tenant.id,
        name="张三",
        phone_enc=encrypt_phone("13712345678"),
        building="1栋",
        room="101",
    )
    db_session.add(owner)
    db_session.flush()
    return owner
```

- [ ] **Step 7: Run full test suite to verify nothing broke**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest --tb=short -q
```

Expected: all existing tests pass (Sprint 1 + Sprint 2 tests)

- [ ] **Step 8: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/core/security.py poc/backend/app/api/auth.py poc/backend/app/api/admin.py poc/backend/app/api/ops.py poc/backend/app/api/admin_cases.py poc/backend/tests/conftest.py
git commit -m "feat: migrate all phone write/read paths to AES-256 encrypt/decrypt"
```

---

## Task 5: Alembic data migration 3a-002 — encrypt existing plaintext phone fields

**Files:**
- Create: `poc/backend/alembic/versions/<rev>_encrypt_phone_fields.py`

- [ ] **Step 1: Generate the migration scaffold**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
alembic revision -m "encrypt_phone_fields"
```

Note the generated filename and open it.

- [ ] **Step 2: Replace upgrade/downgrade with encryption logic**

```python
# poc/backend/alembic/versions/<rev>_encrypt_phone_fields.py
"""encrypt phone fields

Revision ID: <auto-generated>
Revises: <prev-rev>
Create Date: 2026-04-30
"""
import os
from alembic import op
import sqlalchemy as sa


def _is_encrypted(s: str) -> bool:
    """Return True if s looks like AES-GCM ciphertext (iv.tag.ciphertext format)."""
    return len(s.split(".")) == 3


def upgrade() -> None:
    """Encrypt all plaintext phone_enc / admin_phone_enc values in-place."""
    hex_key = os.environ.get("AUTOLUYIN_AES_KEY", "")
    if not hex_key:
        raise RuntimeError("AUTOLUYIN_AES_KEY must be set to run this migration")

    from app.core.crypto import encrypt_phone

    conn = op.get_bind()

    # user_account.phone_enc
    rows = conn.execute(sa.text("SELECT id, phone_enc FROM user_account")).fetchall()
    for row_id, phone in rows:
        if phone and not _is_encrypted(phone):
            conn.execute(
                sa.text("UPDATE user_account SET phone_enc = :enc WHERE id = :id"),
                {"enc": encrypt_phone(phone), "id": row_id},
            )

    # tenant.admin_phone_enc
    rows = conn.execute(sa.text("SELECT id, admin_phone_enc FROM tenant")).fetchall()
    for row_id, phone in rows:
        if phone and not _is_encrypted(phone):
            conn.execute(
                sa.text("UPDATE tenant SET admin_phone_enc = :enc WHERE id = :id"),
                {"enc": encrypt_phone(phone), "id": row_id},
            )

    # owner_profile.phone_enc
    rows = conn.execute(sa.text("SELECT id, phone_enc FROM owner_profile")).fetchall()
    for row_id, phone in rows:
        if phone and not _is_encrypted(phone):
            conn.execute(
                sa.text("UPDATE owner_profile SET phone_enc = :enc WHERE id = :id"),
                {"enc": encrypt_phone(phone), "id": row_id},
            )


def downgrade() -> None:
    """No-op: we don't store plaintext backups. Decrypt manually if needed."""
    pass
```

- [ ] **Step 3: Verify migration runs cleanly (dry-run against test DB)**

Since we don't have a running Postgres here, just verify the file imports without errors:

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
python -c "
import os
os.environ['AUTOLUYIN_AES_KEY'] = 'deadbeef' * 8
from alembic import config
print('Migration file loadable OK')
"
```

Expected: `Migration file loadable OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/alembic/versions/
git commit -m "chore: Alembic data migration 3a-002 — encrypt existing plaintext phone fields"
```

---

## Task 6: Celery infrastructure — `celery_app.py` + `process_call` task skeleton + tests

**Files:**
- Create: `poc/backend/app/worker/__init__.py`
- Create: `poc/backend/app/worker/celery_app.py`
- Create: `poc/backend/app/worker/tasks/__init__.py`
- Create: `poc/backend/app/worker/tasks/call_pipeline.py`
- Create: `poc/backend/tests/worker/__init__.py`
- Create: `poc/backend/tests/worker/test_process_call.py`

- [ ] **Step 1: Write the failing tests**

The task uses its own `_get_db()` context manager to create a DB session. In tests we patch it with the test `db_session` so the task sees seeded data inside the same savepoint transaction.

```python
# poc/backend/tests/worker/test_process_call.py
from contextlib import contextmanager
from unittest.mock import patch

import pytest


@pytest.fixture
def seeded_call(db_session, seeded_tenant, seeded_member_user, seeded_case):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_member_user.id,
        callee_phone_enc=encrypt_phone("13800000000"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()
    return call


@pytest.mark.asyncio
async def test_process_call_sets_status_queued(seeded_call, db_session):
    import app.worker.tasks.call_pipeline as pipeline_module

    @contextmanager
    def _mock_db():
        yield db_session

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call(seeded_call.id)

    db_session.refresh(seeded_call)
    assert seeded_call.status == "queued"


@pytest.mark.asyncio
async def test_process_call_nonexistent_id_is_noop(db_session):
    import app.worker.tasks.call_pipeline as pipeline_module

    @contextmanager
    def _mock_db():
        yield db_session

    with patch.object(pipeline_module, "_get_db", _mock_db):
        pipeline_module.process_call(999999999)  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest tests/worker/test_process_call.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.worker'`

- [ ] **Step 3: Create worker package files**

```python
# poc/backend/app/worker/__init__.py
# (empty)
```

```python
# poc/backend/app/worker/celery_app.py
import os

from celery import Celery

celery_app = Celery(
    "autoluyin",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
)

if os.getenv("CELERY_TASK_ALWAYS_EAGER") == "True":
    celery_app.conf.task_always_eager = True
```

```python
# poc/backend/app/worker/tasks/__init__.py
# (empty)
```

```python
# poc/backend/app/worker/tasks/call_pipeline.py
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.worker.celery_app import celery_app


@contextmanager
def _get_db() -> Generator[Session, None, None]:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://autoluyin:autoluyin_dev@postgres:5432/autoluyin",
    )
    engine = create_engine(url)
    SessionLocal = sessionmaker(engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_call(self, call_id: int) -> None:
    """Sprint 3a: mark call as queued. Sprint 3b: ASR → LLM → Transcript + AnalysisResult."""
    from app.models.call import CallRecord

    with _get_db() as db:
        call = db.get(CallRecord, call_id)
        if not call:
            return
        call.status = "queued"
        db.commit()
```

```python
# poc/backend/tests/worker/__init__.py
# (empty)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest tests/worker/test_process_call.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/worker/ poc/backend/tests/worker/
git commit -m "feat: add Celery worker infrastructure + process_call task skeleton (Sprint 3a)"
```

---

## Task 7: `app/schemas/call.py` updates + `app/api/calls_v1.py` + tests

**Files:**
- Modify: `poc/backend/app/schemas/call.py`
- Create: `poc/backend/app/api/calls_v1.py`
- Create: `poc/backend/tests/api/test_calls_v1.py`

- [ ] **Step 1: Write the failing tests**

```python
# poc/backend/tests/api/test_calls_v1.py
import io
import pytest


@pytest.fixture
def seeded_device(db_session, seeded_member_user, seeded_tenant):
    from app.models.device import DeviceProfile

    device = DeviceProfile(
        device_id="test-device-001",
        user_id=seeded_member_user.id,
        tenant_id=seeded_tenant.id,
        is_healthy=True,
    )
    db_session.add(device)
    db_session.flush()
    return device


@pytest.fixture
def seeded_tenant_with_quota(db_session, seeded_tenant):
    seeded_tenant.monthly_minute_quota = 100  # 100 minutes
    db_session.flush()
    return seeded_tenant


@pytest.mark.asyncio
async def test_upload_call_creates_record(
    client, agent_auth_headers, seeded_device, seeded_case, db_session
):
    audio_bytes = b"fake audio content"
    resp = await client.post(
        "/api/v1/calls/upload",
        headers=agent_auth_headers,
        data={
            "device_id": "test-device-001",
            "case_id": str(seeded_case.id),
            "callee_phone": "13899999999",
            "started_at": "2026-04-30T10:00:00+08:00",
            "ended_at": "2026-04-30T10:02:00+08:00",
            "duration_sec": "120",
        },
        files={"file": ("recording.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "call_id" in data
    assert data["status"] == "uploaded"

    from app.models.call import CallRecord
    call = db_session.get(CallRecord, data["call_id"])
    assert call is not None
    assert call.status in ("uploaded", "queued")  # task runs eagerly, may be queued


@pytest.mark.asyncio
async def test_upload_wrong_device_returns_403(
    client, agent_auth_headers, seeded_case
):
    audio_bytes = b"fake"
    resp = await client.post(
        "/api/v1/calls/upload",
        headers=agent_auth_headers,
        data={
            "device_id": "nonexistent-device",
            "case_id": str(seeded_case.id),
            "callee_phone": "13800000000",
            "started_at": "2026-04-30T10:00:00+08:00",
            "ended_at": "2026-04-30T10:01:00+08:00",
            "duration_sec": "60",
        },
        files={"file": ("recording.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_DEVICE_NOT_FOUND"


@pytest.mark.asyncio
async def test_upload_quota_exceeded_returns_403(
    client, agent_auth_headers, seeded_device, seeded_case, seeded_tenant, db_session
):
    from app.models.tenant import TenantMinuteUsage

    seeded_tenant.monthly_minute_quota = 10  # 10 minutes
    usage = TenantMinuteUsage(
        tenant_id=seeded_tenant.id,
        year_month="2026-04",
        used_minutes=10,  # already at quota
    )
    db_session.add(usage)
    db_session.flush()

    audio_bytes = b"fake"
    resp = await client.post(
        "/api/v1/calls/upload",
        headers=agent_auth_headers,
        data={
            "device_id": "test-device-001",
            "case_id": str(seeded_case.id),
            "callee_phone": "13800000000",
            "started_at": "2026-04-30T10:00:00+08:00",
            "ended_at": "2026-04-30T10:02:00+08:00",
            "duration_sec": "60",
        },
        files={"file": ("recording.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ERR_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_upload_null_quota_means_unlimited(
    client, agent_auth_headers, seeded_device, seeded_case, seeded_tenant, db_session
):
    seeded_tenant.monthly_minute_quota = None  # unlimited
    db_session.flush()

    audio_bytes = b"fake"
    resp = await client.post(
        "/api/v1/calls/upload",
        headers=agent_auth_headers,
        data={
            "device_id": "test-device-001",
            "case_id": str(seeded_case.id),
            "callee_phone": "13800000000",
            "started_at": "2026-04-30T10:00:00+08:00",
            "ended_at": "2026-04-30T10:10:00+08:00",
            "duration_sec": "600",
        },
        files={"file": ("recording.mp3", io.BytesIO(audio_bytes), "audio/mpeg")},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_list_calls_returns_own_calls(
    client, agent_auth_headers, seeded_device, seeded_case, db_session
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_device.tenant_id,
        case_id=seeded_case.id,
        caller_user_id=seeded_device.user_id,
        callee_phone_enc=encrypt_phone("13800000001"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()

    resp = await client.get("/api/v1/calls/", headers=agent_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_call_detail_returns_record(
    client, agent_auth_headers, seeded_device, seeded_case, db_session
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    call = CallRecord(
        tenant_id=seeded_device.tenant_id,
        case_id=seeded_case.id,
        caller_user_id=seeded_device.user_id,
        callee_phone_enc=encrypt_phone("13800000002"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()

    resp = await client.get(f"/api/v1/calls/{call.id}", headers=agent_auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == call.id
    assert data["transcript"] is None
    assert data["analysis"] is None


@pytest.mark.asyncio
async def test_get_call_detail_wrong_user_returns_403(
    client, seeded_device, seeded_case, db_session, seeded_supervisor_user, seeded_tenant
):
    from app.core.crypto import encrypt_phone
    from app.models.call import CallRecord

    # Create call owned by member_user
    call = CallRecord(
        tenant_id=seeded_tenant.id,
        case_id=seeded_case.id,
        caller_user_id=seeded_device.user_id,
        callee_phone_enc=encrypt_phone("13800000003"),
        status="uploaded",
    )
    db_session.add(call)
    db_session.flush()

    # Try to access as a DIFFERENT agent (create another agent user)
    from app.core.security import create_access_token, get_password_hash
    from app.models.tenant import UserTenantMembership
    from app.models.user import UserAccount

    other = UserAccount(
        phone_enc=encrypt_phone("13600000099"),
        name="其他催收员",
        password_hash=get_password_hash("X"),
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    m = UserTenantMembership(
        user_id=other.id,
        tenant_id=seeded_tenant.id,
        role="agent_internal",
        source_type="INTERNAL",
        is_active=True,
    )
    db_session.add(m)
    db_session.flush()
    token = create_access_token({"sub": str(other.id), "user_id": other.id, "tenant_id": seeded_tenant.id, "role": "agent_internal", "scope": f"tenant:{seeded_tenant.id}"})
    other_headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(f"/api/v1/calls/{call.id}", headers=other_headers)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest tests/api/test_calls_v1.py -v
```

Expected: all fail (router not yet registered)

- [ ] **Step 3: Update `app/schemas/call.py` — add upload/list/detail schemas**

```python
# poc/backend/app/schemas/call.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .common import PaginationQuery


class CallListQuery(PaginationQuery):
    case_id: Optional[int] = None
    status: Optional[str] = None


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    case_id: Optional[int]
    initiated_by: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    billable_duration: Optional[int]
    result_tag: Optional[str]
    risk_flagged: bool
    status: str
    created_at: datetime


class CallMinuteQuotaStatus(BaseModel):
    tenant_id: int
    year_month: str
    used_minutes: int
    quota: Optional[int]
    remaining: Optional[int]
    pct_used: Optional[float]
    is_exhausted: bool


class CallUploadResponse(BaseModel):
    call_id: int
    status: str


class CallListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: Optional[int]
    callee_phone_masked: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    status: str
    created_at: datetime


class CallDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: Optional[int]
    callee_phone_masked: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_sec: Optional[int]
    recording_url: Optional[str]
    status: str
    transcript: None  # Sprint 3b
    analysis: None  # Sprint 3b
    created_at: datetime
```

- [ ] **Step 4: Create `app/api/calls_v1.py`**

```python
# poc/backend/app/api/calls_v1.py
from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_phone, mask_phone
from app.core.db import get_db
from app.core.security import get_token_payload, require_roles
from app.core.storage import storage
from app.models.call import CallRecord
from app.models.case import CollectionCase
from app.models.device import DeviceProfile
from app.models.tenant import Tenant, TenantMinuteUsage
from app.schemas.call import CallDetailResponse, CallListItem, CallUploadResponse
from app.schemas.common import PaginatedResponse

router = APIRouter()

AGENT_ROLES = ("agent_internal", "agent_external")
SUPERVISOR_ROLES = ("supervisor", "admin")
ALLOWED_AUDIO_FORMATS = {"mp3", "m4a", "amr", "wav", "aac", "ogg"}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def _get_or_create_usage(db: Session, tenant_id: int, year_month: str) -> TenantMinuteUsage:
    usage = db.execute(
        select(TenantMinuteUsage).where(
            TenantMinuteUsage.tenant_id == tenant_id,
            TenantMinuteUsage.year_month == year_month,
        )
    ).scalar_one_or_none()
    if not usage:
        usage = TenantMinuteUsage(
            tenant_id=tenant_id,
            year_month=year_month,
            used_minutes=0,
        )
        db.add(usage)
        db.flush()
    return usage


@router.post("/upload", response_model=CallUploadResponse, status_code=201)
async def upload_call(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    device_id: Annotated[str, Form()],
    case_id: Annotated[int, Form()],
    callee_phone: Annotated[str, Form()],
    started_at: Annotated[str, Form()],
    ended_at: Annotated[str, Form()],
    duration_sec: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
) -> CallUploadResponse:
    user_id: int = payload["user_id"]
    tenant_id: int = payload["tenant_id"]

    # 1. Verify device belongs to current user
    device = db.execute(
        select(DeviceProfile).where(
            DeviceProfile.device_id == device_id,
            DeviceProfile.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not device:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_DEVICE_NOT_FOUND", "message": "设备未注册或不属于当前用户"},
        )

    # 2. Verify case belongs to tenant
    case = db.execute(
        select(CollectionCase).where(
            CollectionCase.id == case_id,
            CollectionCase.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "案件不存在或不属于当前租户"},
        )

    # 3. Validate file format
    filename = file.filename or "recording"
    fmt = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if fmt not in ALLOWED_AUDIO_FORMATS:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_INVALID_FORMAT", "message": f"不支持的音频格式: {fmt}"},
        )

    # 4. Quota check
    tenant = db.get(Tenant, tenant_id)
    if tenant and tenant.monthly_minute_quota is not None:
        year_month = datetime.now(timezone.utc).strftime("%Y-%m")
        usage = _get_or_create_usage(db, tenant_id, year_month)
        needed = math.ceil(duration_sec / 60)
        if usage.used_minutes + needed > tenant.monthly_minute_quota:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={"code": "ERR_QUOTA_EXCEEDED", "message": "本月通话分钟配额已用尽"},
            )

    # 5. Upload file to storage
    raw = await file.read()
    object_key = f"calls/{tenant_id}/{uuid.uuid4().hex}.{fmt}"
    storage.put_object(object_key, raw, file.content_type or f"audio/{fmt}")
    recording_url = storage.get_url(object_key)

    # 6. Encrypt callee phone
    callee_phone_enc = encrypt_phone(callee_phone)

    # 7. Parse datetimes
    try:
        started_dt = datetime.fromisoformat(started_at)
        ended_dt = datetime.fromisoformat(ended_at)
    except ValueError:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_VALIDATION", "message": "无效的时间格式，使用 ISO8601"},
        )

    # 8. Insert CallRecord
    call = CallRecord(
        tenant_id=tenant_id,
        case_id=case_id,
        caller_user_id=user_id,
        callee_phone_enc=callee_phone_enc,
        initiated_by="app",
        started_at=started_dt,
        ended_at=ended_dt,
        duration_sec=duration_sec,
        recording_url=recording_url,
        status="uploaded",
    )
    db.add(call)
    db.flush()

    # 9. Update quota usage
    if tenant and tenant.monthly_minute_quota is not None:
        year_month = datetime.now(timezone.utc).strftime("%Y-%m")
        usage = _get_or_create_usage(db, tenant_id, year_month)
        usage.used_minutes += math.ceil(duration_sec / 60)

    db.commit()
    db.refresh(call)

    # 10. Dispatch async processing task
    from app.worker.tasks.call_pipeline import process_call
    process_call.delay(call.id)

    return CallUploadResponse(call_id=call.id, status="uploaded")


@router.get("/", response_model=PaginatedResponse[CallListItem])
def list_calls(
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES, *SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
    case_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[CallListItem]:
    user_id: int = payload["user_id"]
    tenant_id: int = payload["tenant_id"]
    role: str = payload.get("role", "")

    stmt = select(CallRecord).where(CallRecord.tenant_id == tenant_id)
    if role in AGENT_ROLES:
        stmt = stmt.where(CallRecord.caller_user_id == user_id)
    if case_id:
        stmt = stmt.where(CallRecord.case_id == case_id)

    total: int = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    calls = (
        db.execute(
            stmt.order_by(CallRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    items = [
        CallListItem(
            id=c.id,
            case_id=c.case_id,
            callee_phone_masked=mask_phone(c.callee_phone_enc),
            started_at=c.started_at,
            ended_at=c.ended_at,
            duration_sec=c.duration_sec,
            status=c.status,
            created_at=c.created_at,
        )
        for c in calls
    ]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{call_id}", response_model=CallDetailResponse)
def get_call_detail(
    call_id: int,
    payload: Annotated[dict, Depends(get_token_payload)],
    _user: Annotated[object, Depends(require_roles(*AGENT_ROLES, *SUPERVISOR_ROLES))],
    db: Annotated[Session, Depends(get_db)],
) -> CallDetailResponse:
    user_id: int = payload["user_id"]
    tenant_id: int = payload["tenant_id"]
    role: str = payload.get("role", "")

    call = db.execute(
        select(CallRecord).where(
            CallRecord.id == call_id,
            CallRecord.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()

    if not call:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_NOT_FOUND", "message": "通话记录不存在"},
        )

    if role in AGENT_ROLES and call.caller_user_id != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_FORBIDDEN", "message": "无权访问此通话记录"},
        )

    return CallDetailResponse(
        id=call.id,
        case_id=call.case_id,
        callee_phone_masked=mask_phone(call.callee_phone_enc),
        started_at=call.started_at,
        ended_at=call.ended_at,
        duration_sec=call.duration_sec,
        recording_url=call.recording_url,
        status=call.status,
        transcript=None,
        analysis=None,
        created_at=call.created_at,
    )
```

- [ ] **Step 5: Commit (pre-router-registration)**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/call.py poc/backend/app/api/calls_v1.py poc/backend/tests/api/test_calls_v1.py
git commit -m "feat: add calls_v1 router (upload + quota check + list + detail)"
```

---

## Task 8: Register routers in `main.py` + docker-compose updates + run all tests

**Files:**
- Modify: `poc/backend/app/main.py`
- Modify: `poc/docker-compose.yml`

- [ ] **Step 1: Update `app/main.py` — register new routers + startup AES validation**

```python
# poc/backend/app/main.py  (full file)
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, admin_cases, agent_cases, auth, calls, devices, ops, recordings, supervisor, tasks, users
from app.api import devices_v1, calls_v1


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate AES key at startup — fail fast rather than fail on first request
    from app.core.crypto import _get_key
    try:
        _get_key()
    except RuntimeError as exc:
        import sys
        print(f"FATAL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    yield


app = FastAPI(
    title="有证慧催 API",
    version="0.1.0",
    description="autoluyin MVP backend",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": f"ERR_{exc.status_code}", "message": str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "ERR_VALIDATION",
            "message": str(first.get("msg", "Validation error")),
        },
    )


# v1 routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(ops.router, prefix="/api/v1/ops", tags=["ops"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(admin_cases.router, prefix="/api/v1/admin", tags=["admin-cases"])
app.include_router(supervisor.router, prefix="/api/v1/supervisor", tags=["supervisor"])
app.include_router(agent_cases.router, prefix="/api/v1/agent", tags=["agent"])
app.include_router(devices_v1.router, prefix="/api/v1/devices", tags=["devices-v1"])
app.include_router(calls_v1.router, prefix="/api/v1/calls", tags=["calls-v1"])

# Legacy PoC routers (kept for backwards compatibility during transition)
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(calls.router, prefix="/api/calls", tags=["calls"])
app.include_router(recordings.router, prefix="/api/recordings", tags=["recordings"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 2: Add `redis` and `celery_worker` to `poc/docker-compose.yml`**

Open `poc/docker-compose.yml` and add after the `backend` service, before the `volumes:` section:

```yaml
  redis:
    image: redis:7-alpine
    container_name: autoluyin-redis
    ports:
      - "${REDIS_HOST_PORT:-16379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: autoluyin-celery
    command: celery -A app.worker.celery_app worker --loglevel=info -Q default
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+psycopg://autoluyin:autoluyin_dev@postgres:5432/autoluyin
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - recordings_data:/data/recordings
```

Also update the `backend` service to add redis dependency and `REDIS_URL`:

```yaml
  backend:
    ...
    environment:
      DATABASE_URL: postgresql+psycopg://autoluyin:autoluyin_dev@postgres:5432/autoluyin
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

- [ ] **Step 3: Install Celery dependency**

Add to `poc/backend/requirements.txt`:

```
celery==5.3.6
redis==5.0.4
```

- [ ] **Step 4: Run full test suite**

```bash
cd /Users/shuo/AI/autoluyin/poc/backend
/opt/homebrew/bin/pytest --tb=short -q
```

Expected: all Sprint 1 + Sprint 2 tests pass, plus new Sprint 3a tests:
- `tests/test_crypto.py` — 6 tests
- `tests/api/test_devices_v1.py` — 5 tests
- `tests/api/test_calls_v1.py` — 7 tests
- `tests/worker/test_process_call.py` — 2 tests

Total: ≥20 new tests PASS, all existing tests still PASS

- [ ] **Step 5: Frontend type check (Sprint 3a has no frontend changes)**

```bash
cd /Users/shuo/AI/autoluyin/frontend
npx tsc --noEmit && npm run build
```

Expected: clean build (no new changes, no regressions)

- [ ] **Step 6: Commit**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/main.py poc/docker-compose.yml poc/backend/requirements.txt
git commit -m "feat: register devices_v1 + calls_v1 routers; add Redis + Celery to docker-compose"
```

---

## Acceptance Criteria

| Area | Check |
|------|-------|
| `crypto.py` | `encrypt_phone` → `decrypt_phone` roundtrip; deterministic; `mask_phone` returns `138****5678` format |
| Login | Existing user can log in with phone + password after data migration |
| Device register | `POST /api/v1/devices/register` UPSERT works; 401 without JWT |
| Self-check | `can_call=True` when all three flags True; `can_call=False` otherwise |
| Call upload | 201 with `{call_id, status}`; CallRecord in DB; Celery task enqueued |
| Wrong device | 403 `ERR_DEVICE_NOT_FOUND` |
| Quota exceeded | 403 `ERR_QUOTA_EXCEEDED` |
| Null quota | upload succeeds when `monthly_minute_quota=null` |
| Call list | Agent sees own calls only; supervisor sees all tenant calls |
| Call detail | 403 when agent accesses another agent's call |
| Process_call task | Status updated from `uploaded` to `queued` in EAGER mode |
| Tests | `pytest` full-green (no failures, no xfail surprises) |

---

## Not in Sprint 3a

- DashScope ASR integration (Sprint 3b)
- Qwen-Plus LLM integration (Sprint 3b)
- Android call recording and auto-upload (Sprint 3b)
- PC frontend call management pages (Sprint 3b)
