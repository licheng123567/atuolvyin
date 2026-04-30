from __future__ import annotations

import base64
import hashlib
import hmac as _hmac

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_KEY: bytes | None = None


def _get_key() -> bytes:
    global _KEY
    if _KEY is None:
        from app.core.config import settings  # 延迟导入避免循环依赖
        hex_key = settings.autoluyin_aes_key
        if len(hex_key) != 64:
            raise RuntimeError(
                "AUTOLUYIN_AES_KEY must be set to 64 hex characters (32 bytes); "
                f"got length {len(hex_key)}"
            )
        try:
            _KEY = bytes.fromhex(hex_key)
        except ValueError as exc:
            raise RuntimeError(
                "AUTOLUYIN_AES_KEY contains invalid characters; must be 64 hex digits (0-9, a-f)"
            ) from exc
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
        raise ValueError(
            f"Invalid cipher format: expected 3 dot-separated parts, got {len(parts)!r}"
        )
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
