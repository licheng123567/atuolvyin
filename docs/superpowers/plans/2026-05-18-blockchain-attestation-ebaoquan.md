# 区块链存证接入（易保全证据保全）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把第三方「易保全证据保全」(ebaoquan.org) API 接入区块链存证链路，让案件法务存证包里的录音 + 转写 + AI 分析真实上链。

**Architecture:** 配置驱动分发 —— `app/services/blockchain.py` 的 `submit_attestation()` 按 active `BlockchainConfig.provider` 选择 mock（本地确定性 tx_hash，dev/测试默认）或 ebaoquan（真实上链）。新增纯 HTTP 客户端模块 `app/services/ebaoquan.py`（签名 + `createEvidenceHash` + `queryEvidenceDetail`，永不抛异常）。`evidence_bundle.py` 在生成案件存证包时对每通电话的三类数据各上链一次，单条失败不阻断 ZIP 生成。

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + Alembic + httpx + pytest/testcontainers；前端 TypeScript + React + Refine.dev。

**设计依据：** `docs/superpowers/specs/2026-05-18-blockchain-attestation-ebaoquan-design.md`

**前置：** 所有后端命令在 `poc/backend/` 下执行；测试用 `python3.12 -m pytest`（host 上跑，testcontainers 自起 Postgres）。实现前先建分支 `git checkout -b feat/blockchain-ebaoquan`（当前在 `main`，禁止直接在 main 实现）。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `app/models/platform.py` | `BlockchainConfig` 加 `app_key` 列 | 改 |
| `app/models/blockchain_attestation.py` | `tx_hash`/`block_height` 放宽 + 易保全字段 | 改 |
| `alembic/versions/24021_v220_blockchain_ebaoquan.py` | 数据库迁移 | 建 |
| `app/services/ebaoquan.py` | 易保全 API 客户端（签名 + 两端点，纯 HTTP seam） | 建 |
| `app/services/blockchain.py` | `submit_attestation` 重构 + mock/ebaoquan 分发 | 改 |
| `app/services/evidence_bundle.py` | 录音/转写/分析三类上链 + `blockchain` 字段改列表 | 改 |
| `app/schemas/platform.py` | `BlockchainConfigIn/Out` 加 `app_key` + provider 枚举加 `ebaoquan` | 改 |
| `app/api/super_config.py` | `/super/blockchain-config` 处理 `app_key` | 改 |
| `frontend/src/pages/super/blockchain-config/index.tsx` | 配置页加 `app_key` 字段 + 易保全选项 | 改 |
| `tests/test_blockchain_attestation_model.py` | 模型列回归 | 建 |
| `tests/services/test_ebaoquan.py` | 签名 + 客户端测试 | 建 |
| `tests/services/test_blockchain_attestation.py` | `submit_attestation` 分发测试 | 建 |
| `tests/api/test_super_config.py` | `app_key` 端点测试 | 改 |
| `tests/api/test_legal_evidence_bundle.py` | 适配 `blockchain` 列表结构 + 三类上链 | 改 |

---

## Task 1: 数据模型 + Alembic 迁移

**Files:**
- Modify: `poc/backend/app/models/platform.py`（`BlockchainConfig` 类，68-89 行）
- Modify: `poc/backend/app/models/blockchain_attestation.py`（44-60 行）
- Create: `poc/backend/alembic/versions/24021_v220_blockchain_ebaoquan.py`
- Test: `poc/backend/tests/test_blockchain_attestation_model.py`

- [ ] **Step 1: 写失败测试**

创建 `poc/backend/tests/test_blockchain_attestation_model.py`：

```python
"""易保全接入 Task 1 — BlockchainConfig / BlockchainAttestation 模型列回归。"""
from __future__ import annotations

from datetime import UTC, datetime

from app.models.blockchain_attestation import BlockchainAttestation
from app.models.platform import BlockchainConfig


def test_blockchain_config_accepts_app_key(db_session):
    cfg = BlockchainConfig(
        provider="ebaoquan",
        api_endpoint="https://bs.sandbox.ebaoquan.org",
        app_key="a7ce728fbec40519",
        api_key_enc=None,
        is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()
    db_session.refresh(cfg)
    assert cfg.app_key == "a7ce728fbec40519"


def test_attestation_allows_null_tx_hash_and_ebaoquan_fields(db_session, seeded_tenant):
    now = datetime.now(UTC)
    att = BlockchainAttestation(
        tenant_id=seeded_tenant.id,
        data_sha256="a" * 64,
        data_sha512="b" * 128,
        data_type="transcript",
        chain_provider="ebaoquan",
        chain_endpoint="https://bs.sandbox.ebaoquan.org",
        tx_hash=None,
        block_height=None,
        provider_evidence_id=96111,
        preservation_id=1852,
        status="confirmed",
        submitted_at=now,
        confirmed_at=now,
    )
    db_session.add(att)
    db_session.flush()
    db_session.refresh(att)
    assert att.tx_hash is None
    assert att.block_height is None
    assert att.provider_evidence_id == 96111
    assert att.preservation_id == 1852
    assert att.data_sha512 == "b" * 128
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/test_blockchain_attestation_model.py -v`
Expected: FAIL —— `TypeError: 'app_key' is an invalid keyword argument` / `'provider_evidence_id' is an invalid keyword argument`。

- [ ] **Step 3: 改 `BlockchainConfig` 模型**

在 `poc/backend/app/models/platform.py` 的 `BlockchainConfig` 类，`api_key_enc` 列之后加 `app_key`：

```python
class BlockchainConfig(Base):
    __tablename__ = "blockchain_config"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(
        sa.String(64), nullable=False
    )  # ebaoquan / antchain / fisco-bcos / mock
    api_endpoint: Mapped[str] = mapped_column(sa.Text, nullable=False)
    api_key_enc: Mapped[str | None] = mapped_column(sa.Text, nullable=True)  # AES-256 (appKeySecret)
    app_key: Mapped[str | None] = mapped_column(
        sa.String(128), nullable=True
    )  # 易保全公钥标识 appKey，非密钥，明文存
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

    __table_args__ = (sa.UniqueConstraint("provider", name="uq_blockchain_config_provider"),)
```

- [ ] **Step 4: 改 `BlockchainAttestation` 模型**

在 `poc/backend/app/models/blockchain_attestation.py`，把 `data_sha256` 之后到 `block_height` 这段（44-52 行）改为：

```python
    data_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    data_sha512: Mapped[str | None] = mapped_column(
        sa.String(128), nullable=True
    )  # 送易保全的 SHA-512 hex
    data_type: Mapped[str] = mapped_column(
        sa.String(32), nullable=False
    )  # "call_recording" / "transcript" / "analysis" / "evidence_bundle"

    chain_provider: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    chain_endpoint: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # mock 分支填本地 tx_hash + block_height；易保全分支留 NULL。
    tx_hash: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, unique=True)
    block_height: Mapped[int | None] = mapped_column(sa.BigInteger, nullable=True)
    # 易保全分支字段
    provider_evidence_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True
    )  # 易保全 evidenceId
    preservation_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, nullable=True
    )  # 易保全保全备案号
```

（`status` / `submitted_at` / `confirmed_at` / `payload_metadata` / `__table_args__` 不动。）

- [ ] **Step 5: 创建 Alembic 迁移**

创建 `poc/backend/alembic/versions/24021_v220_blockchain_ebaoquan.py`：

```python
"""易保全接入 — blockchain_config.app_key + blockchain_attestation 易保全字段

Revision ID: 24021v220g
Revises: 24020v220f
Create Date: 2026-05-18 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "24021v220g"
down_revision: str | None = "24020v220f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "blockchain_config",
        sa.Column("app_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "blockchain_attestation",
        sa.Column("data_sha512", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "blockchain_attestation",
        sa.Column("provider_evidence_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "blockchain_attestation",
        sa.Column("preservation_id", sa.BigInteger(), nullable=True),
    )
    op.alter_column(
        "blockchain_attestation", "tx_hash", existing_type=sa.String(length=64), nullable=True
    )
    op.alter_column(
        "blockchain_attestation", "block_height", existing_type=sa.BigInteger(), nullable=True
    )


def downgrade() -> None:
    # 注意：若已存在易保全存证（tx_hash/block_height 为 NULL），下面的 NOT NULL 还原会失败 ——
    # 这是创建了 NULL 数据的迁移天然不可完全逆转的情形，downgrade 仅用于无数据的回滚。
    op.alter_column(
        "blockchain_attestation", "block_height", existing_type=sa.BigInteger(), nullable=False
    )
    op.alter_column(
        "blockchain_attestation", "tx_hash", existing_type=sa.String(length=64), nullable=False
    )
    op.drop_column("blockchain_attestation", "preservation_id")
    op.drop_column("blockchain_attestation", "provider_evidence_id")
    op.drop_column("blockchain_attestation", "data_sha512")
    op.drop_column("blockchain_config", "app_key")
```

- [ ] **Step 6: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/test_blockchain_attestation_model.py -v`
Expected: PASS（2 passed）。conftest 用 `Base.metadata.create_all`，模型改动即生效。

- [ ] **Step 7: 验证迁移可应用**

Run: `cd poc/backend && python3.12 -m pytest tests/test_alembic_roundtrip.py -v`
Expected: PASS —— 该测试新起 Postgres 容器跑 `upgrade head`，会执行新迁移 `24021v220g`。

- [ ] **Step 8: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/models/platform.py poc/backend/app/models/blockchain_attestation.py poc/backend/alembic/versions/24021_v220_blockchain_ebaoquan.py poc/backend/tests/test_blockchain_attestation_model.py
git commit -m "feat(blockchain): BlockchainConfig.app_key + 存证表易保全字段 + 迁移"
```

---

## Task 2: 易保全签名函数 `sign_params`

**Files:**
- Create: `poc/backend/app/services/ebaoquan.py`
- Test: `poc/backend/tests/services/test_ebaoquan.py`

- [ ] **Step 1: 写失败测试**

创建 `poc/backend/tests/services/test_ebaoquan.py`：

```python
"""易保全接入 Task 2/3 — ebaoquan 客户端测试。"""
from __future__ import annotations

from app.services.ebaoquan import sign_params


def test_sign_params_doc_vector():
    """证据保全 API 文档 §4.1 给出的签名示例向量。"""
    params = {
        "appKey": "a7ce728fbec40519",
        "param1": "paramValue1",
        "param2": "paramValue2",
        "param3": "paramValue3",
    }
    sign = sign_params(params, "d5207ae9f7bee0692a1e4014f90e1af0")
    assert sign == "2523044EB55944A10324AAAA3DCCEB75"


def test_sign_params_excludes_sign_key():
    """已有 sign 键不参与签名计算。"""
    base = {"appKey": "k", "evidenceId": "96111"}
    with_sign = dict(base, sign="STALE")
    assert sign_params(with_sign, "secret") == sign_params(base, "secret")


def test_sign_params_is_order_independent():
    """参数按 key ASCII 排序，传入顺序不影响结果。"""
    a = sign_params({"b": "2", "a": "1"}, "s")
    b = sign_params({"a": "1", "b": "2"}, "s")
    assert a == b
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_ebaoquan.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.ebaoquan'`。

- [ ] **Step 3: 创建 `ebaoquan.py` 含 `sign_params`**

创建 `poc/backend/app/services/ebaoquan.py`：

```python
"""易保全证据保全（ebaoquan.org）API 客户端。

纯 HTTP seam，不碰 DB，永不抛异常。公开函数：
  - sign_params()           证据保全 API 文档 §4.1 签名算法
  - create_evidence_hash()  HASH 保全 → EbaoquanHashResult
  - query_evidence_detail() 证据详情（取保全备案号）→ EbaoquanDetailResult
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10.0


@dataclass(frozen=True)
class EbaoquanHashResult:
    ok: bool
    evidence_id: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class EbaoquanDetailResult:
    ok: bool
    preservation_id: int | None = None
    error: str | None = None


def sign_params(params: dict[str, str], app_key_secret: str) -> str:
    """易保全签名 §4.1：参数（排除 sign）按 key ASCII 升序拼 k=v&k=v，
    尾接 appKeySecret，MD5 后全大写。"""
    items = sorted((k, v) for k, v in params.items() if k != "sign")
    string_a = "&".join(f"{k}={v}" for k, v in items)
    string_sign_temp = string_a + app_key_secret
    return hashlib.md5(string_sign_temp.encode("utf-8")).hexdigest().upper()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_ebaoquan.py -v`
Expected: PASS（3 passed）。若 `test_sign_params_doc_vector` 失败，说明文档示例与 MD5 实算不符 —— 停下核对文档 §4.1，不要改测试期望值掩盖问题。

- [ ] **Step 5: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/services/ebaoquan.py poc/backend/tests/services/test_ebaoquan.py
git commit -m "feat(blockchain): 易保全签名算法 sign_params"
```

---

## Task 3: 易保全 HTTP 客户端 `create_evidence_hash` / `query_evidence_detail`

**Files:**
- Modify: `poc/backend/app/services/ebaoquan.py`
- Test: `poc/backend/tests/services/test_ebaoquan.py`

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/services/test_ebaoquan.py` 末尾追加：

```python
import httpx

from app.services import ebaoquan
from app.services.ebaoquan import create_evidence_hash, query_evidence_detail


def test_create_evidence_hash_success(monkeypatch):
    captured = {}

    def fake_post(url: str, params: dict, timeout: float) -> dict:
        captured["url"] = url
        captured["params"] = params
        return {"success": True, "message": None, "code": 0, "data": {"evidenceId": 96111}}

    monkeypatch.setattr(ebaoquan, "_post", fake_post)
    result = create_evidence_hash(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        file_hash="f" * 128,
        name="案件1通话2录音",
        description="测试物业公司",
        evidence_type="3",
    )
    assert result.ok is True
    assert result.evidence_id == 96111
    assert captured["url"] == "https://bs.sandbox.ebaoquan.org/api/createEvidenceHash"
    # sign 已带上且非空
    assert captured["params"]["sign"]
    assert captured["params"]["type"] == "3"


def test_create_evidence_hash_business_failure(monkeypatch):
    def fake_post(url: str, params: dict, timeout: float) -> dict:
        return {"success": False, "message": "name 不正确", "code": 7201001, "data": None}

    monkeypatch.setattr(ebaoquan, "_post", fake_post)
    result = create_evidence_hash(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        file_hash="f" * 128,
        name="x",
        description="",
        evidence_type="3",
    )
    assert result.ok is False
    assert result.evidence_id is None
    assert "name 不正确" in result.error


def test_create_evidence_hash_http_exception(monkeypatch):
    def raise_timeout(url: str, params: dict, timeout: float) -> dict:
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(ebaoquan, "_post", raise_timeout)
    result = create_evidence_hash(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        file_hash="f" * 128,
        name="x",
        description="",
        evidence_type="3",
    )
    assert result.ok is False
    assert result.error == "ERR_EBAOQUAN_HTTP"


def test_query_evidence_detail_success(monkeypatch):
    def fake_post(url: str, params: dict, timeout: float) -> dict:
        assert url.endswith("/api/queryEvidenceDetail")
        return {
            "success": True,
            "message": None,
            "code": 0,
            "data": {"evidenceId": 96, "preservationId": 1852, "type": 1},
        }

    monkeypatch.setattr(ebaoquan, "_post", fake_post)
    result = query_evidence_detail(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        evidence_id=96,
    )
    assert result.ok is True
    assert result.preservation_id == 1852


def test_query_evidence_detail_http_exception(monkeypatch):
    def raise_err(url: str, params: dict, timeout: float) -> dict:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(ebaoquan, "_post", raise_err)
    result = query_evidence_detail(
        base_url="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        app_key_secret="secret1",
        evidence_id=96,
    )
    assert result.ok is False
    assert result.error == "ERR_EBAOQUAN_HTTP"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_ebaoquan.py -v`
Expected: FAIL —— `ImportError: cannot import name 'create_evidence_hash'` / `module ... has no attribute '_post'`。

- [ ] **Step 3: 在 `ebaoquan.py` 加 `_post` + 两个端点函数**

在 `poc/backend/app/services/ebaoquan.py` 的 `sign_params` 之后追加：

```python
def _post(url: str, params: dict[str, str], timeout: float) -> dict[str, Any]:
    """真实 HTTP POST（form-urlencoded），返回解析后的 JSON。失败抛异常。

    测试通过 monkeypatch 替换本函数以模拟易保全响应。
    """
    with httpx.Client(timeout=timeout) as cli:
        resp = cli.post(url, data=params)
    resp.raise_for_status()
    return resp.json()


def create_evidence_hash(
    *,
    base_url: str,
    app_key: str,
    app_key_secret: str,
    file_hash: str,
    name: str,
    description: str,
    evidence_type: str,
    timeout: float = _HTTP_TIMEOUT,
) -> EbaoquanHashResult:
    """HASH 保全：POST /api/createEvidenceHash。永不抛异常。"""
    params: dict[str, str] = {
        "appKey": app_key,
        "fileHash": file_hash,
        "name": name,
        "description": description,
        "type": evidence_type,
    }
    params["sign"] = sign_params(params, app_key_secret)
    url = base_url.rstrip("/") + "/api/createEvidenceHash"
    try:
        data = _post(url, params, timeout)
    except Exception as exc:  # noqa: BLE001 — 外部 HTTP 任何异常都不应冒泡
        logger.warning("易保全 createEvidenceHash HTTP 调用失败: %s", exc)
        return EbaoquanHashResult(ok=False, error="ERR_EBAOQUAN_HTTP")

    if data.get("code") == 0:
        payload = data.get("data") or {}
        evidence_id = payload.get("evidenceId")
        if evidence_id is None:
            return EbaoquanHashResult(ok=False, error="ERR_EBAOQUAN_NO_EVIDENCE_ID")
        return EbaoquanHashResult(ok=True, evidence_id=int(evidence_id))

    reason = str(data.get("message") or f"code={data.get('code')}")
    return EbaoquanHashResult(ok=False, error=reason)


def query_evidence_detail(
    *,
    base_url: str,
    app_key: str,
    app_key_secret: str,
    evidence_id: int,
    timeout: float = _HTTP_TIMEOUT,
) -> EbaoquanDetailResult:
    """证据详情：POST /api/queryEvidenceDetail，取保全备案号。永不抛异常。"""
    params: dict[str, str] = {
        "appKey": app_key,
        "evidenceId": str(evidence_id),
    }
    params["sign"] = sign_params(params, app_key_secret)
    url = base_url.rstrip("/") + "/api/queryEvidenceDetail"
    try:
        data = _post(url, params, timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning("易保全 queryEvidenceDetail HTTP 调用失败: %s", exc)
        return EbaoquanDetailResult(ok=False, error="ERR_EBAOQUAN_HTTP")

    if data.get("code") == 0:
        payload = data.get("data") or {}
        pid = payload.get("preservationId")
        return EbaoquanDetailResult(
            ok=True, preservation_id=int(pid) if pid is not None else None
        )

    reason = str(data.get("message") or f"code={data.get('code')}")
    return EbaoquanDetailResult(ok=False, error=reason)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_ebaoquan.py -v`
Expected: PASS（8 passed）。

- [ ] **Step 5: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/services/ebaoquan.py poc/backend/tests/services/test_ebaoquan.py
git commit -m "feat(blockchain): 易保全 createEvidenceHash / queryEvidenceDetail 客户端"
```

---

## Task 4: `submit_attestation` 重构 —— 收字节 + mock/ebaoquan 分发

**Files:**
- Modify: `poc/backend/app/services/blockchain.py`（整文件重写）
- Modify: `poc/backend/app/services/evidence_bundle.py`（调用点 218-244 行，最小适配保持绿）
- Test: `poc/backend/tests/services/test_blockchain_attestation.py`

- [ ] **Step 1: 写失败测试**

创建 `poc/backend/tests/services/test_blockchain_attestation.py`：

```python
"""易保全接入 Task 4 — submit_attestation mock/ebaoquan 分发测试。"""
from __future__ import annotations

from app.core.crypto import encrypt_phone
from app.models.platform import BlockchainConfig
from app.services import blockchain
from app.services.blockchain import submit_attestation
from app.services.ebaoquan import EbaoquanDetailResult, EbaoquanHashResult


def test_mock_branch_when_no_config(db_session, seeded_tenant):
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"recording-bytes",
        data_type="call_recording",
        title="案件1通话1录音",
    )
    assert att.status == "confirmed"
    assert att.chain_provider == "mock"
    assert att.tx_hash is not None and len(att.tx_hash) == 64
    assert att.block_height >= 1
    assert att.data_sha512 is not None and len(att.data_sha512) == 128


def test_mock_branch_when_non_ebaoquan_provider(db_session, seeded_tenant):
    db_session.add(
        BlockchainConfig(
            provider="antchain",
            api_endpoint="https://antchain.example/attest",
            is_active=True,
        )
    )
    db_session.flush()
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="transcript",
        title="t",
    )
    assert att.chain_provider == "antchain"
    assert att.tx_hash is not None


def test_ebaoquan_success(db_session, seeded_tenant, monkeypatch):
    db_session.add(
        BlockchainConfig(
            provider="ebaoquan",
            api_endpoint="https://bs.sandbox.ebaoquan.org",
            app_key="appkey1",
            api_key_enc=encrypt_phone("secret1"),
            is_active=True,
        )
    )
    db_session.flush()

    monkeypatch.setattr(
        blockchain.ebaoquan,
        "create_evidence_hash",
        lambda **kw: EbaoquanHashResult(ok=True, evidence_id=96111),
    )
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "query_evidence_detail",
        lambda **kw: EbaoquanDetailResult(ok=True, preservation_id=1852),
    )
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"recording-bytes",
        data_type="call_recording",
        title="案件1通话1录音",
    )
    assert att.status == "confirmed"
    assert att.chain_provider == "ebaoquan"
    assert att.tx_hash is None
    assert att.block_height is None
    assert att.provider_evidence_id == 96111
    assert att.preservation_id == 1852


def test_ebaoquan_success_but_detail_lookup_fails(db_session, seeded_tenant, monkeypatch):
    db_session.add(
        BlockchainConfig(
            provider="ebaoquan",
            api_endpoint="https://bs.sandbox.ebaoquan.org",
            app_key="appkey1",
            api_key_enc=encrypt_phone("secret1"),
            is_active=True,
        )
    )
    db_session.flush()
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "create_evidence_hash",
        lambda **kw: EbaoquanHashResult(ok=True, evidence_id=96111),
    )
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "query_evidence_detail",
        lambda **kw: EbaoquanDetailResult(ok=False, error="ERR_EBAOQUAN_HTTP"),
    )
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="analysis",
        title="t",
    )
    assert att.status == "confirmed"
    assert att.provider_evidence_id == 96111
    assert att.preservation_id is None


def test_ebaoquan_create_failure_records_config_failure(db_session, seeded_tenant, monkeypatch):
    cfg = BlockchainConfig(
        provider="ebaoquan",
        api_endpoint="https://bs.sandbox.ebaoquan.org",
        app_key="appkey1",
        api_key_enc=encrypt_phone("secret1"),
        is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "create_evidence_hash",
        lambda **kw: EbaoquanHashResult(ok=False, error="name 不正确"),
    )
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="transcript",
        title="t",
    )
    assert att.status == "failed"
    db_session.refresh(cfg)
    assert cfg.last_failure_at is not None
    assert "name 不正确" in cfg.last_failure_reason


def test_ebaoquan_active_but_missing_credentials(db_session, seeded_tenant):
    cfg = BlockchainConfig(
        provider="ebaoquan",
        api_endpoint="https://bs.sandbox.ebaoquan.org",
        app_key=None,
        api_key_enc=None,
        is_active=True,
    )
    db_session.add(cfg)
    db_session.flush()
    att = submit_attestation(
        db_session,
        tenant_id=seeded_tenant.id,
        data=b"x",
        data_type="call_recording",
        title="t",
    )
    assert att.status == "failed"
    assert att.payload_metadata.get("error") == "ERR_BLOCKCHAIN_NOT_CONFIGURED"
    db_session.refresh(cfg)
    assert cfg.last_failure_reason == "ERR_BLOCKCHAIN_NOT_CONFIGURED"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_blockchain_attestation.py -v`
Expected: FAIL —— `submit_attestation()` 当前签名是 `data_sha256=` 而非 `data=`，报 `TypeError` / 缺 `title` 参数。

- [ ] **Step 3: 重写 `blockchain.py`**

把 `poc/backend/app/services/blockchain.py` 整文件替换为：

```python
"""Sprint 13.1 / v2.2 — 区块链存证服务（PRD §20.3）。

submit_attestation() 是唯一公开入口，按 active BlockchainConfig.provider 分发：
  - mock（无 active 配置 / provider≠ebaoquan / 未激活）：本地确定性 tx_hash + 自增 block_height。
  - ebaoquan：调易保全 createEvidenceHash，成功后 best-effort 补查保全备案号。
provider 失败永不抛异常 —— 落 status="failed" 记录 + 写回 BlockchainConfig.last_failure_*。
调用方负责 db.commit()。
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_phone
from app.models.blockchain_attestation import BlockchainAttestation
from app.models.platform import BlockchainConfig
from app.services import ebaoquan

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "mock"
MOCK_ENDPOINT = "https://mock.blockchain.local/v1/attest"

# data_type → 易保全证据类型（1图片/2文档/3音频/4视频/99其他）
_EBAOQUAN_TYPE = {
    "call_recording": "3",
    "transcript": "2",
    "analysis": "2",
    "evidence_bundle": "99",
}


def _resolve_config(db: Session) -> BlockchainConfig | None:
    """取最新一行 BlockchainConfig（单行平台配置）。"""
    return db.execute(
        select(BlockchainConfig).order_by(desc(BlockchainConfig.updated_at)).limit(1)
    ).scalar_one_or_none()


def _next_block_height(db: Session) -> int:
    """模拟自增 block_height —— mock 分支用，取 max+1。"""
    current = db.execute(
        select(func.coalesce(func.max(BlockchainAttestation.block_height), 0))
    ).scalar_one()
    return int(current) + 1


def _gen_tx_hash(provider: str, data_sha256: str, nonce: str) -> str:
    """生成确定性 + 唯一的 64 字符 tx_hash（mock 分支用）。"""
    h = hashlib.sha256()
    h.update(provider.encode())
    h.update(b":")
    h.update(data_sha256.encode())
    h.update(b":")
    h.update(nonce.encode())
    return h.hexdigest()


def _record_config_failure(config: BlockchainConfig, reason: str) -> None:
    """写回 BlockchainConfig.last_failure_*（随调用方的 commit 一并提交）。"""
    config.last_failure_at = datetime.now(UTC)
    config.last_failure_reason = reason[:500]


def submit_attestation(
    db: Session,
    *,
    tenant_id: int,
    data: bytes,
    data_type: str,
    title: str,
    description: str | None = None,
    payload_metadata: dict[str, Any] | None = None,
    call_id: int | None = None,
    legal_case_id: int | None = None,
) -> BlockchainAttestation:
    """同步"上链"并返回 attestation 记录。

    - data: 被存证数据的原始字节（须与写入 ZIP 的字节一致）。
    - data_type: call_recording / transcript / analysis / evidence_bundle。
    - title / description: 易保全证据名称 / 备注（内部各截断 50 字）。
    - provider 失败永不抛异常 —— 落 status="failed" 记录。
    - db.flush()，调用方负责 commit。
    """
    if not data:
        raise ValueError("data 不能为空")

    data_sha256 = hashlib.sha256(data).hexdigest()
    data_sha512 = hashlib.sha512(data).hexdigest()
    now = datetime.now(UTC)
    config = _resolve_config(db)

    use_ebaoquan = (
        config is not None and config.provider == "ebaoquan" and config.is_active
    )

    if not use_ebaoquan:
        # ── mock 分支（行为与历史一致）──
        provider = config.provider if config is not None else DEFAULT_PROVIDER
        endpoint = config.api_endpoint if config is not None else MOCK_ENDPOINT
        nonce = secrets.token_hex(16)
        record = BlockchainAttestation(
            tenant_id=tenant_id,
            call_id=call_id,
            legal_case_id=legal_case_id,
            data_sha256=data_sha256,
            data_sha512=data_sha512,
            data_type=data_type,
            chain_provider=provider,
            chain_endpoint=endpoint,
            tx_hash=_gen_tx_hash(provider, data_sha256, nonce),
            block_height=_next_block_height(db),
            status="confirmed",
            submitted_at=now,
            confirmed_at=now,
            payload_metadata=payload_metadata,
        )
        db.add(record)
        db.flush()
        return record

    # ── 易保全分支 ──
    assert config is not None  # use_ebaoquan 已保证
    record = BlockchainAttestation(
        tenant_id=tenant_id,
        call_id=call_id,
        legal_case_id=legal_case_id,
        data_sha256=data_sha256,
        data_sha512=data_sha512,
        data_type=data_type,
        chain_provider="ebaoquan",
        chain_endpoint=config.api_endpoint,
        tx_hash=None,
        block_height=None,
        status="failed",
        submitted_at=now,
        confirmed_at=None,
        payload_metadata=dict(payload_metadata or {}),
    )

    if not config.app_key or not config.api_key_enc:
        record.payload_metadata["error"] = "ERR_BLOCKCHAIN_NOT_CONFIGURED"
        _record_config_failure(config, "ERR_BLOCKCHAIN_NOT_CONFIGURED")
        db.add(record)
        db.flush()
        return record

    try:
        app_key_secret = decrypt_phone(config.api_key_enc)
    except Exception:
        logger.exception("BlockchainConfig.api_key_enc 解密失败")
        record.payload_metadata["error"] = "ERR_BLOCKCHAIN_NOT_CONFIGURED"
        _record_config_failure(config, "ERR_BLOCKCHAIN_NOT_CONFIGURED")
        db.add(record)
        db.flush()
        return record

    hash_result = ebaoquan.create_evidence_hash(
        base_url=config.api_endpoint,
        app_key=config.app_key,
        app_key_secret=app_key_secret,
        file_hash=data_sha512,
        name=title[:50],
        description=(description or "")[:50],
        evidence_type=_EBAOQUAN_TYPE.get(data_type, "99"),
    )

    if not hash_result.ok or hash_result.evidence_id is None:
        reason = hash_result.error or "ERR_EBAOQUAN_FAILED"
        record.payload_metadata["error"] = reason
        _record_config_failure(config, reason)
        db.add(record)
        db.flush()
        return record

    record.status = "confirmed"
    record.confirmed_at = datetime.now(UTC)
    record.provider_evidence_id = hash_result.evidence_id

    # best-effort 补查保全备案号 —— 失败不降级 confirmed 状态
    detail = ebaoquan.query_evidence_detail(
        base_url=config.api_endpoint,
        app_key=config.app_key,
        app_key_secret=app_key_secret,
        evidence_id=hash_result.evidence_id,
    )
    if detail.ok and detail.preservation_id is not None:
        record.preservation_id = detail.preservation_id

    db.add(record)
    db.flush()
    return record
```

- [ ] **Step 4: 最小适配 `evidence_bundle.py` 调用点保持绿**

`evidence_bundle.py` 当前唯一调用点（218-233 行）传的是 `data_sha256=recording_sha`，签名已变。把 218-233 行那段 `if recording_sha:` 块改为：

```python
            # 区块链上链（仅当有录音）
            blockchain_meta: dict[str, Any]
            if recording_sha:
                att = blockchain_svc.submit_attestation(
                    db,
                    tenant_id=tenant_id,
                    data=audio,
                    data_type="call_recording",
                    title=f"案件{case.id}通话{call.id}录音",
                    description=tenant.name if tenant else None,
                    call_id=call.id,
                    legal_case_id=legal_case_id,
                    payload_metadata={
                        "tenant_name": tenant.name if tenant else None,
                        "call_id": call.id,
                        "case_id": case.id,
                        "started_at": call.started_at.isoformat() if call.started_at else None,
                        "duration_sec": call.duration_sec,
                    },
                )
                blockchain_meta = _attestation_to_blockchain_meta(att)
```

（`audio` 在 `if call.object_key:` 块内已赋值；`recording_sha` 为真即保证 `audio` 已绑定。`else` 分支的 `skipped_no_recording` meta 与其余代码不动 —— Task 5 再做列表化改造。）

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/services/test_blockchain_attestation.py tests/api/test_legal_evidence_bundle.py tests/api/test_public_verify.py -v`
Expected: PASS —— `test_blockchain_attestation.py` 6 passed；evidence_bundle / public_verify 既有测试仍绿（mock 分支行为不变）。

- [ ] **Step 6: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/services/blockchain.py poc/backend/app/services/evidence_bundle.py poc/backend/tests/services/test_blockchain_attestation.py
git commit -m "feat(blockchain): submit_attestation 收字节 + mock/易保全分发"
```

---

## Task 5: `evidence_bundle.py` —— 录音/转写/分析三类上链

**Files:**
- Modify: `poc/backend/app/services/evidence_bundle.py`（`_attestation_to_blockchain_meta` 56-65 行；call 循环 137-263 行）
- Test: `poc/backend/tests/api/test_legal_evidence_bundle.py`（更新既有断言 + 加新测试）

- [ ] **Step 1: 更新既有测试 + 写新测试（确认失败）**

`test_legal_evidence_bundle.py` 现有两处把 `attestation["blockchain"]` 当对象访问，改造后是列表。把 `test_bundle_blockchain_unconfigured` 末尾 4 行断言（396-399 行）改为：

```python
    # Sprint 13.1 — 无 BlockchainConfig 时落到 mock provider，仍产出真实 tx_hash
    chain = attestation["blockchain"]
    assert isinstance(chain, list)
    rec = next(m for m in chain if m["data_type"] == "call_recording")
    assert rec["provider"] == "mock"
    assert rec["status"] == "confirmed"
    assert len(rec["transaction_id"]) == 64
    assert rec["block_height"] >= 1
```

把 `test_bundle_blockchain_active_provider` 末尾 4 行断言（435-438 行）改为：

```python
    chain = attestation["blockchain"]
    rec = next(m for m in chain if m["data_type"] == "call_recording")
    assert rec["provider"] == "antchain"
    assert rec["endpoint"].endswith("/attest")
    assert rec["status"] == "confirmed"
    assert len(rec["transaction_id"]) == 64
```

在文件末尾追加新测试（验证三类上链 + 易保全失败不阻断）：

```python
@pytest.mark.asyncio
async def test_bundle_attests_recording_transcript_analysis(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
):
    """一通有录音 + 转写 + 分析的电话 → blockchain 列表含 3 条 mock 存证。"""
    from app.models.call import AnalysisResult, Transcript

    call, _ = _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user, audio_bytes=b"audio"
    )
    db_session.add(Transcript(call_id=call.id, full_text="业主你好，关于物业费"))
    db_session.add(
        AnalysisResult(
            call_id=call.id,
            summary="业主承诺月底缴费",
            key_segments=[],
            needs_review=False,
        )
    )
    db_session.flush()

    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    attestation = json.loads(
        zf.read(f"case_{seeded_case.id}/calls/call_{call.id}/attestation.json")
    )
    chain = attestation["blockchain"]
    data_types = {m["data_type"] for m in chain}
    assert data_types == {"call_recording", "transcript", "analysis"}
    assert all(m["status"] == "confirmed" for m in chain)


@pytest.mark.asyncio
async def test_bundle_ebaoquan_failure_does_not_block(
    client: AsyncClient,
    db_session,
    seeded_tenant,
    seeded_case,
    seeded_legal_case,
    seeded_member_user,
    legal_auth_headers,
    monkeypatch,
):
    """易保全上链失败 → ZIP 仍生成，attestation.json 的 blockchain 项标 failed。"""
    from app.models.platform import BlockchainConfig
    from app.services import blockchain
    from app.services.ebaoquan import EbaoquanHashResult

    db_session.add(
        BlockchainConfig(
            provider="ebaoquan",
            api_endpoint="https://bs.sandbox.ebaoquan.org",
            app_key="appkey1",
            api_key_enc=encrypt_phone("secret1"),
            is_active=True,
        )
    )
    db_session.flush()
    monkeypatch.setattr(
        blockchain.ebaoquan,
        "create_evidence_hash",
        lambda **kw: EbaoquanHashResult(ok=False, error="系统错误"),
    )

    call, _ = _make_call_with_recording(
        db_session, seeded_tenant, seeded_case, seeded_member_user, audio_bytes=b"audio"
    )
    resp = await client.get(
        f"/api/v1/legal/cases/{seeded_legal_case.id}/evidence-bundle",
        headers=legal_auth_headers,
    )
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    attestation = json.loads(
        zf.read(f"case_{seeded_case.id}/calls/call_{call.id}/attestation.json")
    )
    rec = next(m for m in attestation["blockchain"] if m["data_type"] == "call_recording")
    assert rec["provider"] == "ebaoquan"
    assert rec["status"] == "failed"
    assert rec["transaction_id"] is None
```

确认 `encrypt_phone` 已在该测试文件 import；若无，在文件顶部加 `from app.core.crypto import encrypt_phone`。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_legal_evidence_bundle.py -v`
Expected: FAIL —— `blockchain` 仍是单对象，新断言（`isinstance(chain, list)`、`data_type` 等）不通过。

- [ ] **Step 3: 改 `_attestation_to_blockchain_meta`**

把 `evidence_bundle.py` 的 `_attestation_to_blockchain_meta`（56-65 行）替换为：

```python
def _attestation_to_blockchain_meta(att: Any) -> dict[str, Any]:
    return {
        "data_type": att.data_type,
        "provider": att.chain_provider,
        "endpoint": att.chain_endpoint,
        "status": att.status,
        "transaction_id": att.tx_hash,
        "block_height": att.block_height,
        "evidence_id": att.provider_evidence_id,
        "preservation_id": att.preservation_id,
        "submitted_at": att.submitted_at.isoformat() if att.submitted_at else None,
        "verify_url": f"/verify/{att.tx_hash}" if att.tx_hash else None,
    }
```

- [ ] **Step 4: 改 call 循环 —— 捕获三类字节 + 列表化上链**

在 call 循环里捕获三类原始字节。`recording_bytes` —— 在 `if call.object_key:` 块内、`recording_sha = hashlib.sha256(audio).hexdigest()` 那行之后加一行 `recording_bytes = audio`；并在 `recording_sha: str | None = None` 那行（141 行）下方加 `recording_bytes: bytes | None = None`。

转写 —— 把 `_write(f"{call_dir}/transcript.txt", transcript.full_text.encode("utf-8"))`（174 行）改为：

```python
                transcript_bytes = transcript.full_text.encode("utf-8")
                _write(f"{call_dir}/transcript.txt", transcript_bytes)
```

并在 `transcript_sha: str | None = None`（172 行）下方加 `transcript_bytes: bytes | None = None`。

分析 —— 把写 `analysis.json` 那段（202-206 行）改为：

```python
                analysis_bytes = json.dumps(
                    analysis_payload, ensure_ascii=False, indent=2
                ).encode("utf-8")
                _write(f"{call_dir}/analysis.json", analysis_bytes)
                analysis_sha = files_index[-1]["sha256"]
```

并在 `analysis_sha: str | None = None`（195 行）下方加 `analysis_bytes: bytes | None = None`。

然后把「区块链上链」整段（即 Task 4 Step 4 改过的 `if recording_sha:` / `else:` 块，216-244 行的 `blockchain_meta` 构造）整体替换为：

```python
            # 区块链上链 —— 录音 / 转写 / 分析各上一次，单条失败不阻断
            blockchain_metas: list[dict[str, Any]] = []
            _attest_targets: list[tuple[str, bytes | None, str]] = [
                ("call_recording", recording_bytes, f"案件{case.id}通话{call.id}录音"),
                ("transcript", transcript_bytes, f"案件{case.id}通话{call.id}转写"),
                ("analysis", analysis_bytes, f"案件{case.id}通话{call.id}AI分析"),
            ]
            for _dtype, _payload, _title in _attest_targets:
                if _payload is None:
                    continue
                att = blockchain_svc.submit_attestation(
                    db,
                    tenant_id=tenant_id,
                    data=_payload,
                    data_type=_dtype,
                    title=_title,
                    description=tenant.name if tenant else None,
                    call_id=call.id,
                    legal_case_id=legal_case_id,
                    payload_metadata={
                        "tenant_name": tenant.name if tenant else None,
                        "call_id": call.id,
                        "case_id": case.id,
                        "data_type": _dtype,
                        "started_at": call.started_at.isoformat()
                        if call.started_at
                        else None,
                        "duration_sec": call.duration_sec,
                    },
                )
                blockchain_metas.append(_attestation_to_blockchain_meta(att))
```

最后把 `attestation` dict 里的 `"blockchain": blockchain_meta`（258 行）改为 `"blockchain": blockchain_metas`。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_legal_evidence_bundle.py tests/api/test_public_verify.py -v`
Expected: PASS —— 既有测试（已更新断言）+ 2 个新测试全绿。

- [ ] **Step 6: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/services/evidence_bundle.py poc/backend/tests/api/test_legal_evidence_bundle.py
git commit -m "feat(blockchain): 存证包对录音/转写/分析三类数据上链"
```

---

## Task 6: 超管 Schema + API —— `app_key`

**Files:**
- Modify: `poc/backend/app/schemas/platform.py`（`BlockchainConfigIn/Out`，110-125 行）
- Modify: `poc/backend/app/api/super_config.py`（`_config_to_out` 135-145 行；`put_blockchain_config` 159-183 行）
- Test: `poc/backend/tests/api/test_super_config.py`

- [ ] **Step 1: 写失败测试**

在 `poc/backend/tests/api/test_super_config.py` 的 blockchain config 测试区（`# ── L1972 blockchain config ──` 之后）追加：

```python
@pytest.mark.asyncio
async def test_blockchain_config_put_ebaoquan_with_app_key(
    client: AsyncClient, super_auth_headers
):
    body = {
        "provider": "ebaoquan",
        "api_endpoint": "https://bs.sandbox.ebaoquan.org",
        "app_key": "a7ce728fbec40519",
        "api_key": "appkeysecret-plain",
        "is_active": True,
    }
    put = await client.put(
        "/api/v1/super/blockchain-config", json=body, headers=super_auth_headers
    )
    assert put.status_code == 200
    data = put.json()
    assert data["provider"] == "ebaoquan"
    assert data["app_key"] == "a7ce728fbec40519"
    assert data["has_api_key"] is True
    # 明文密钥绝不回传
    assert "api_key" not in data
    assert "appkeysecret-plain" not in str(data)

    get = await client.get(
        "/api/v1/super/blockchain-config", headers=super_auth_headers
    )
    assert get.json()["app_key"] == "a7ce728fbec40519"


@pytest.mark.asyncio
async def test_blockchain_config_ebaoquan_requires_super(
    client: AsyncClient, ops_auth_headers
):
    resp = await client.get(
        "/api/v1/super/blockchain-config", headers=ops_auth_headers
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_super_config.py -k blockchain -v`
Expected: FAIL —— `provider="ebaoquan"` 不在 Literal 内（422）/ 响应无 `app_key` 键。

- [ ] **Step 3: 改 Schema**

在 `poc/backend/app/schemas/platform.py`，把 `BlockchainConfigIn` 和 `BlockchainConfigOut`（110-125 行）改为：

```python
class BlockchainConfigIn(BaseModel):
    provider: Literal["ebaoquan", "antchain", "fisco-bcos", "mock"]
    api_endpoint: str = Field(min_length=1, max_length=500)
    app_key: str | None = Field(None, max_length=128)
    api_key: str | None = Field(None, max_length=500)  # appKeySecret；None 时不改
    is_active: bool = False


class BlockchainConfigOut(BaseModel):
    id: int
    provider: str
    api_endpoint: str
    app_key: str | None  # 公钥标识，可回显
    has_api_key: bool  # never echo the appKeySecret back
    is_active: bool
    last_failure_at: datetime | None
    last_failure_reason: str | None
    updated_at: datetime
```

- [ ] **Step 4: 改 `super_config.py`**

把 `_config_to_out`（135-145 行）改为：

```python
def _config_to_out(c: BlockchainConfig) -> BlockchainConfigOut:
    return BlockchainConfigOut(
        id=c.id,
        provider=c.provider,
        api_endpoint=c.api_endpoint,
        app_key=c.app_key,
        has_api_key=bool(c.api_key_enc),
        is_active=c.is_active,
        last_failure_at=c.last_failure_at,
        last_failure_reason=c.last_failure_reason,
        updated_at=c.updated_at,
    )
```

把 `put_blockchain_config` 的 upsert 体（168-180 行的 `if c is None:` / `else:` 两支）改为：

```python
    if c is None:
        c = BlockchainConfig(
            provider=body.provider,
            api_endpoint=body.api_endpoint,
            app_key=body.app_key,
            api_key_enc=encrypt_phone(body.api_key) if body.api_key else None,
            is_active=body.is_active,
        )
        db.add(c)
    else:
        c.api_endpoint = body.api_endpoint
        c.app_key = body.app_key
        if body.api_key is not None:
            c.api_key_enc = encrypt_phone(body.api_key) if body.api_key else None
        c.is_active = body.is_active
```

- [ ] **Step 5: 跑测试确认通过**

Run: `cd poc/backend && python3.12 -m pytest tests/api/test_super_config.py -v`
Expected: PASS —— blockchain config 既有测试 + 2 个新测试全绿。

- [ ] **Step 6: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add poc/backend/app/schemas/platform.py poc/backend/app/api/super_config.py poc/backend/tests/api/test_super_config.py
git commit -m "feat(blockchain): /super/blockchain-config 支持易保全 app_key"
```

---

## Task 7: 前端 —— blockchain-config 配置页加 `app_key` + 易保全选项

**Files:**
- Modify: `frontend/src/pages/super/blockchain-config/index.tsx`

- [ ] **Step 1: 改 `BlockchainConfig` 接口 + provider 选项**

在 `frontend/src/pages/super/blockchain-config/index.tsx`，`BlockchainConfig` 接口加 `app_key`，`PROVIDER_OPTIONS` 加易保全并置首：

```tsx
interface BlockchainConfig {
  id: number;
  provider: string;
  api_endpoint: string;
  app_key: string | null;
  has_api_key: boolean;
  is_active: boolean;
  last_failure_at: string | null;
  last_failure_reason: string | null;
  updated_at: string;
}

const PROVIDER_OPTIONS = [
  { value: "ebaoquan", label: "易保全证据保全" },
  { value: "antchain", label: "蚂蚁链" },
  { value: "fisco-bcos", label: "FISCO BCOS" },
  { value: "mock", label: "Mock（仅测试）" },
];
```

- [ ] **Step 2: 加 `appKey` state + 初始化 + 默认 provider**

把 `provider` 默认值改为 `ebaoquan`，新增 `appKey` state；并在 `useEffect` 初始化里带上 `app_key`：

```tsx
  const [provider, setProvider] = useState("ebaoquan");
  const [endpoint, setEndpoint] = useState("");
  const [appKey, setAppKey] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [isActive, setIsActive] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState("");

  const initRef = useRef(false);
  useEffect(() => {
    if (config && !initRef.current) {
      initRef.current = true;
      setProvider(config.provider);
      setEndpoint(config.api_endpoint);
      setAppKey(config.app_key ?? "");
      setIsActive(config.is_active);
    }
  }, [config]);
```

- [ ] **Step 3: submit 带上 `app_key`**

把 `submit` 里的 `values` 改为：

```tsx
        values: {
          provider,
          api_endpoint: endpoint,
          app_key: appKey || null,
          api_key: apiKey || null,
          is_active: isActive,
        },
```

- [ ] **Step 4: 加 `appKey` 输入框 + endpoint 提示**

在「API Endpoint」输入框的 `<div>` 之后、「API Key」输入框 `<div>` 之前，插入 appKey 输入框：

```tsx
        <div>
          <label className="block text-sm font-medium text-[var(--color-neutral-700)] mb-1">
            appKey（公钥标识）
          </label>
          <input
            type="text"
            value={appKey}
            onChange={(e) => setAppKey(e.target.value)}
            placeholder="易保全 appKey"
            className="w-full px-3 py-2 text-sm border border-[var(--color-neutral-200)]"
            style={{ borderRadius: "var(--radius-md)" }}
          />
        </div>
```

把「API Endpoint」输入框的 `placeholder` 改为 `https://bs.sandbox.ebaoquan.org`，并在该输入框下方加一行提示：

```tsx
          <p className="text-xs text-[var(--color-neutral-400)] mt-1">
            易保全沙箱 https://bs.sandbox.ebaoquan.org · 生产 https://bs.ebaoquan.org
          </p>
```

把「API Key」label 改为 `appKeySecret（密钥）`。

- [ ] **Step 5: typecheck + 构建 + 前端测试**

Run: `cd /Users/shuo/AI/autoluyin/frontend && npm run typecheck && npm run build && npm run test`
Expected: tsc 无报错；build 成功；vitest 全绿（既有 204 passed 不回归）。

- [ ] **Step 6: 提交**

```bash
cd /Users/shuo/AI/autoluyin
git add frontend/src/pages/super/blockchain-config/index.tsx
git commit -m "feat(blockchain): 配置页支持易保全 appKey + provider 选项"
```

---

## 收尾：全量回归

- [ ] **后端全量**

Run: `cd poc/backend && python3.12 -m pytest -q`
Expected: 全绿（基线 884 passed + 本次新增测试，无回归）。

- [ ] **前端全量**

Run: `cd /Users/shuo/AI/autoluyin/frontend && npm run test && npm run build`
Expected: 全绿（基线 204 passed）。

- [ ] **lint**

Run: `cd poc/backend && python3.12 -m ruff check app tests`
Expected: 无报错。

---

## 自检清单（写计划后已核对）

- **Spec 覆盖**：① 数据模型 → Task 1；② `ebaoquan.py` 客户端 → Task 2+3；③ `submit_attestation` 分发 → Task 4；④ 存证包接线 → Task 5；⑤ 超管 API → Task 6；⑥ 前端 → Task 7；错误处理（不抛异常 / `last_failure_*` / 失败原因码）贯穿 Task 3-5；测试每 Task 内含。
- **类型一致**：`submit_attestation(data: bytes, data_type, title, description=...)` 在 Task 4 定义、Task 5 按此调用；`EbaoquanHashResult(ok, evidence_id, error)` / `EbaoquanDetailResult(ok, preservation_id, error)` 在 Task 2/3 定义、Task 4 测试按此构造；`_attestation_to_blockchain_meta` 输出键（`data_type`/`provider`/`status`/`transaction_id`/`evidence_id`/`preservation_id`）在 Task 5 定义、同 Task 测试按此断言。
- **迁移**：revision `24021v220g` 接 head `24020v220f`；`tx_hash`/`block_height` NOT NULL→NULL 安全无回填。
- **绿色链**：Task 4 同步最小适配 `evidence_bundle.py` 调用点，确保每次提交测试套件不破。
