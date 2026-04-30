"""encrypt_phone_fields

Revision ID: 648bbc47c8d6
Revises: f398859a9fb3
Create Date: 2026-04-30 07:30:06.414045

"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '648bbc47c8d6'
down_revision: Union[str, None] = 'f398859a9fb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
