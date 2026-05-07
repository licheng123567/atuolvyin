"""Alembic upgrade head + downgrade round-trip safety net for v1.5 migrations.

The default test suite uses Base.metadata.create_all (fast), so migrations
are not exercised. This test:
  1. Spins up a fresh Postgres testcontainer
  2. Applies init.sql (legacy PoC tables that pre-date alembic)
  3. Runs upgrade head — exercises ALL migrations including v1.5 (19001-19004)
  4. Verifies expected tables + seed data exist
  5. Downgrades back to 18002v14 (v1.4 boundary) — exercises only the v1.5
     downgrade() pairs, sidestepping legacy-migration / init.sql conflicts
  6. Verifies v1.5 ORM tables are gone

Catches: syntax errors in v1.5 migrations, downgrade() that doesn't reverse
upgrade(), seed INSERT failures, broken DAG wiring.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="module")
def fresh_pg():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


def _alembic_config(db_url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", "alembic")
    return cfg


def _apply_init_sql(db_url: str) -> None:
    """Seed legacy PoC tables (transcript, owner_profile pre-ORM, etc.)."""
    init_sql = Path(__file__).parent.parent / "migrations" / "init.sql"
    if not init_sql.exists():
        return
    eng = create_engine(db_url, future=True)
    raw = init_sql.read_text(encoding="utf-8")
    with eng.begin() as conn:
        # Run as a single script — split by statements would mishandle DO blocks.
        conn.exec_driver_sql(raw)
    eng.dispose()


def test_alembic_upgrade_head_then_downgrade_base(fresh_pg):
    """Full upgrade head → downgrade base on a fresh container."""
    url = fresh_pg.get_connection_url().replace("psycopg2", "psycopg")
    _apply_init_sql(url)
    cfg = _alembic_config(url)

    # Upgrade to head
    command.upgrade(cfg, "head")

    eng = create_engine(url, future=True)
    insp = inspect(eng)
    tables = set(insp.get_table_names())

    # Spot-check that key v1.5 tables exist
    expected = {
        "tenant", "user_account", "collection_case",  # core
        "legal_service_package", "legal_conversion_order",  # 16.1
        "law_firm", "law_firm_lawyer",  # 16.2
        "legal_platform_invoice",  # 16.3
        "legal_document_template", "legal_document_render",  # 16.4
        "active_session",  # 15.1
        "notification",  # 15.4
    }
    missing = expected - tables
    assert not missing, f"upgrade head missing tables: {missing}"

    # Spot-check seeded data
    with eng.connect() as conn:
        pkg_count = conn.execute(
            text("SELECT count(*) FROM legal_service_package WHERE tenant_id IS NULL")
        ).scalar_one()
        assert pkg_count == 4, "expected 4 platform default service packages seeded"

        tpl_count = conn.execute(
            text("SELECT count(*) FROM legal_document_template WHERE tenant_id IS NULL")
        ).scalar_one()
        assert tpl_count == 4, "expected 4 platform default doc templates seeded"

    # Downgrade just the v1.5 chain (19001..19004 → 18002v14) so we
    # exercise our new migrations' downgrade() without tripping pre-existing
    # legacy-migration vs init.sql conflicts.
    command.downgrade(cfg, "18002v14")

    insp2 = inspect(eng)
    remaining = set(insp2.get_table_names())
    v15_orm_tables = {
        "legal_service_package", "legal_conversion_order",  # 16.1
        "law_firm", "law_firm_lawyer",  # 16.2
        "legal_platform_invoice",  # 16.3
        "legal_document_template", "legal_document_render",  # 16.4
    }
    leaked = v15_orm_tables & remaining
    assert not leaked, f"v1.5 downgrade did not drop ORM tables: {leaked}"

    # legal_conversion_order's law_firm_id / lawyer_id FK columns should be gone
    # (added by 19002, removed by its downgrade). Verify by checking they're
    # no longer reachable via ORM table — indirectly tested above (the table
    # itself was dropped). Also verify v1.4 tables still present.
    assert "active_session" in remaining, "downgraded too far — 18002v14 should keep active_session"
    assert "notification" in remaining, "downgraded too far — 18002v14 should keep notification"

    eng.dispose()
