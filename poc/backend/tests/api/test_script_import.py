import io
import pytest


def _make_xlsx(rows: list[tuple]) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["话术标题", "异议类型", "话术内容", "编写说明"])
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def seeded_script(db_session, seeded_tenant):
    from app.models.script import ScriptTemplate
    s = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="分期建议",
        trigger_intent="经济困难",
        content="您好，了解到您有资金压力，可以分期缴纳。",
        version=1,
    )
    db_session.add(s)
    db_session.flush()
    return s


@pytest.mark.asyncio
async def test_import_valid_rows(client, admin_auth_headers, db_session, seeded_tenant):
    from app.models.script import ScriptTemplate
    from sqlalchemy import select
    data = _make_xlsx([
        ("分期话术", "经济困难", "可以分期缴纳", "测试说明"),
        ("服务话术", "服务不满", "非常抱歉", None),
    ])
    resp = await client.post(
        "/api/v1/admin/scripts/import",
        headers=admin_auth_headers,
        files={"file": ("test.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] == 2
    assert body["skipped"] == 0
    assert body["failed"] == 0


@pytest.mark.asyncio
async def test_import_skips_duplicate_title(client, admin_auth_headers, seeded_script):
    data = _make_xlsx([("分期建议", "经济困难", "内容", None)])
    resp = await client.post(
        "/api/v1/admin/scripts/import",
        headers=admin_auth_headers,
        files={"file": ("test.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    body = resp.json()
    assert body["skipped"] == 1
    assert body["success"] == 0


@pytest.mark.asyncio
async def test_import_fails_invalid_intent(client, admin_auth_headers):
    data = _make_xlsx([("话术X", "无效类型", "内容", None)])
    resp = await client.post(
        "/api/v1/admin/scripts/import",
        headers=admin_auth_headers,
        files={"file": ("test.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    body = resp.json()
    assert body["failed"] == 1
    assert len(body["errors"]) >= 1
