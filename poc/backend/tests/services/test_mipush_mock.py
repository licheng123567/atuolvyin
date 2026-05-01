import pytest


@pytest.mark.asyncio
async def test_mock_mipush_records_payload():
    from app.services import mipush

    client = mipush.get_mipush_client()
    # Force a fresh mock instance so prior tests don't pollute
    if hasattr(client, "reset"):
        client.reset()
    await client.send_to_user(
        reg_id="reg-abc",
        payload={"type": "DIAL_REQUEST", "call_id": 4711, "case_id": 1023},
        title="新呼叫",
        description="张某某 · 138****1234",
    )
    sent = client.sent_messages
    assert len(sent) == 1
    msg = sent[0]
    assert msg["reg_id"] == "reg-abc"
    assert msg["payload"]["type"] == "DIAL_REQUEST"
    assert msg["payload"]["call_id"] == 4711
    assert msg["title"] == "新呼叫"


@pytest.mark.asyncio
async def test_mock_mipush_singleton_across_calls():
    from app.services import mipush

    a = mipush.get_mipush_client()
    b = mipush.get_mipush_client()
    assert a is b
