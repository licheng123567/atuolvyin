import pytest
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from fastapi import HTTPException


def test_password_hash_and_verify():
    hashed = get_password_hash("mypassword")
    assert hashed != "mypassword"
    assert verify_password("mypassword", hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_create_and_decode_token():
    payload = {"user_id": 42, "tenant_id": 7, "role": "admin", "scope": "tenant:7"}
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded["user_id"] == 42
    assert decoded["tenant_id"] == 7
    assert decoded["role"] == "admin"
    assert "exp" in decoded


def test_decode_invalid_token_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("not.a.valid.token")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "ERR_INVALID_TOKEN"


def test_mask_phone_11_digits():
    from app.core.crypto import encrypt_phone
    from app.core.security import mask_phone
    assert mask_phone(encrypt_phone("13800138001")) == "138****8001"
    assert mask_phone(encrypt_phone("13912345678")) == "139****5678"


def test_mask_phone_short():
    from app.core.crypto import encrypt_phone
    from app.core.security import mask_phone
    result = mask_phone(encrypt_phone("1234567"))
    assert "****" in result
