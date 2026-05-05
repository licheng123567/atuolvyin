import pytest


@pytest.fixture
def seeded_script(db_session, seeded_tenant):
    from app.models.script import ScriptTemplate, ScriptTemplateVersion
    s = ScriptTemplate(
        tenant_id=seeded_tenant.id,
        title="分期建议",
        trigger_intent="经济困难",
        content="您好，了解到您有资金压力，可以分期缴纳。",
        version=1,
    )
    db_session.add(s)
    db_session.flush()
    v = ScriptTemplateVersion(
        script_template_id=s.id, version=1,
        title=s.title, trigger_intent=s.trigger_intent, content=s.content,
    )
    db_session.add(v)
    db_session.flush()
    return s


@pytest.mark.asyncio
async def test_list_scripts_returns_items(client, admin_auth_headers, seeded_script):
    resp = await client.get("/api/v1/admin/scripts", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    ids = [i["id"] for i in body["items"]]
    assert seeded_script.id in ids


@pytest.mark.asyncio
async def test_create_script_writes_snapshot(client, admin_auth_headers, db_session, seeded_tenant):
    from app.models.script import ScriptTemplateVersion
    from sqlalchemy import select
    resp = await client.post(
        "/api/v1/admin/scripts",
        json={"title": "新话术", "trigger_intent": "服务不满", "content": "非常抱歉给您带来不便"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 201, resp.text
    script_id = resp.json()["id"]
    versions = db_session.execute(
        select(ScriptTemplateVersion).where(ScriptTemplateVersion.script_template_id == script_id)
    ).scalars().all()
    assert len(versions) == 1
    assert versions[0].version == 1


@pytest.mark.asyncio
async def test_patch_script_increments_version(client, admin_auth_headers, seeded_script, db_session):
    from app.models.script import ScriptTemplateVersion
    from sqlalchemy import select
    resp = await client.patch(
        f"/api/v1/admin/scripts/{seeded_script.id}",
        json={"content": "更新后的话术内容"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] == 2
    versions = db_session.execute(
        select(ScriptTemplateVersion).where(ScriptTemplateVersion.script_template_id == seeded_script.id)
    ).scalars().all()
    assert len(versions) == 2


@pytest.mark.asyncio
async def test_toggle_script(client, admin_auth_headers, seeded_script):
    resp = await client.post(f"/api/v1/admin/scripts/{seeded_script.id}/toggle", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    resp2 = await client.post(f"/api/v1/admin/scripts/{seeded_script.id}/toggle", headers=admin_auth_headers)
    assert resp2.json()["is_active"] is True


@pytest.mark.asyncio
async def test_delete_requires_inactive(client, admin_auth_headers, seeded_script):
    resp = await client.delete(f"/api/v1/admin/scripts/{seeded_script.id}", headers=admin_auth_headers)
    assert resp.status_code == 400  # still active

    await client.post(f"/api/v1/admin/scripts/{seeded_script.id}/toggle", headers=admin_auth_headers)
    resp2 = await client.delete(f"/api/v1/admin/scripts/{seeded_script.id}", headers=admin_auth_headers)
    assert resp2.status_code == 204


@pytest.mark.asyncio
async def test_versions_list(client, admin_auth_headers, seeded_script):
    resp = await client.get(f"/api/v1/admin/scripts/{seeded_script.id}/versions", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_rollback(client, admin_auth_headers, seeded_script, db_session):
    from app.models.script import ScriptTemplate, ScriptTemplateVersion
    from sqlalchemy import select
    # patch to v2
    await client.patch(
        f"/api/v1/admin/scripts/{seeded_script.id}",
        json={"content": "v2内容"},
        headers=admin_auth_headers,
    )
    resp = await client.post(
        f"/api/v1/admin/scripts/{seeded_script.id}/rollback",
        json={"to_version": 1},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["version"] == 3  # new snapshot = v3

    db_session.expire_all()
    s = db_session.get(ScriptTemplate, seeded_script.id)
    assert s.content == "您好，了解到您有资金压力，可以分期缴纳。"
    versions = db_session.execute(
        select(ScriptTemplateVersion).where(ScriptTemplateVersion.script_template_id == s.id)
    ).scalars().all()
    assert len(versions) == 3
