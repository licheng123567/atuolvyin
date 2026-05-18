"""Phase 2 — SupervisorShift partial unique index 行为测试。

物业侧（provider_id IS NULL）与服务商侧（provider_id 非空）的排班
互不冲突；同一 scope 内同 (tenant, date, slot) 重复则被唯一索引拒绝。
"""
from __future__ import annotations

from datetime import date

import pytest
import sqlalchemy as sa

from app.models.supervisor_shift import SupervisorShift

# ---------------------------------------------------------------------------
# 本文件所需最小 FK 行（tenant + 两个 service_provider）
# 用 autouse fixture 在同一事务内插入，测试结束后随 trans.rollback 一并清理。
# ---------------------------------------------------------------------------

@pytest.fixture
def shift_fk_rows(db_session):
    """在测试事务内创建 tenant=1 和 service_provider id=100,200 的占位行。"""
    from app.core.crypto import encrypt_phone
    from app.models.tenant import ServiceProvider, Tenant

    tenant = Tenant(
        id=1,
        name="测试物业",
        admin_phone_enc=encrypt_phone("13800000001"),
        plan="trial",
        is_active=True,
    )
    prov_a = ServiceProvider(
        id=100,
        name="服务商A",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13800000002"),
    )
    prov_b = ServiceProvider(
        id=200,
        name="服务商B",
        provider_type="collection",
        admin_phone_enc=encrypt_phone("13800000003"),
    )
    db_session.add_all([tenant, prov_a, prov_b])
    db_session.flush()
    return {"tenant": tenant, "prov_a": prov_a, "prov_b": prov_b}


def _shift(tenant_id: int, provider_id: int | None, slot: str = "morning") -> SupervisorShift:
    return SupervisorShift(
        tenant_id=tenant_id,
        provider_id=provider_id,
        shift_date=date(2026, 6, 1),
        slot=slot,
        supervisor_name="督导甲",
    )


def test_property_and_provider_same_slot_coexist(db_session, shift_fk_rows):
    """同 (tenant, date, slot)：物业排班 + 服务商 A 排班 + 服务商 B 排班 可并存。"""
    db_session.add_all([
        _shift(1, None),
        _shift(1, 100),
        _shift(1, 200),
    ])
    db_session.flush()
    rows = db_session.execute(
        sa.select(SupervisorShift).where(SupervisorShift.tenant_id == 1)
    ).scalars().all()
    assert len(rows) == 3


def test_duplicate_property_slot_rejected(db_session, shift_fk_rows):
    """物业侧同 (tenant, date, slot) 重复 → partial unique index 拒绝。"""
    db_session.add(_shift(1, None))
    db_session.flush()
    db_session.add(_shift(1, None))
    with pytest.raises(sa.exc.IntegrityError):
        db_session.flush()


def test_duplicate_provider_slot_rejected(db_session, shift_fk_rows):
    """服务商侧同 (tenant, provider, date, slot) 重复 → partial unique index 拒绝。"""
    db_session.add(_shift(1, 100))
    db_session.flush()
    db_session.add(_shift(1, 100))
    with pytest.raises(sa.exc.IntegrityError):
        db_session.flush()
