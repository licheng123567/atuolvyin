"""merge sprint 5a + 5b heads

Revision ID: 1120fc740bba
Revises: 5a001riskword, 5b001
Create Date: 2026-05-05 12:52:01.402109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1120fc740bba'
down_revision: Union[str, None] = ('5a001riskword', '5b001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
