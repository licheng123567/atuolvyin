import os
import pytest

# 在导入 crypto 模块前设置密钥
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
