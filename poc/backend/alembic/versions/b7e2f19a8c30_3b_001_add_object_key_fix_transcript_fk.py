"""3b_001_add_object_key_fix_transcript_fk

Revision ID: b7e2f19a8c30
Revises: 648bbc47c8d6
Create Date: 2026-04-30

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b7e2f19a8c30'
down_revision: Union[str, None] = '648bbc47c8d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('call_record', sa.Column('object_key', sa.Text(), nullable=True))
    # Drop old FK if it exists (IF EXISTS is atomic on PostgreSQL)
    op.execute(
        "ALTER TABLE transcript DROP CONSTRAINT IF EXISTS transcript_call_id_fkey"
    )
    # Re-create FK pointing to correct table
    op.execute(
        "ALTER TABLE transcript ADD CONSTRAINT fk_transcript_call_record "
        "FOREIGN KEY (call_id) REFERENCES call_record(id)"
    )


def downgrade() -> None:
    op.drop_column('call_record', 'object_key')
