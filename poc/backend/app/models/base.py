from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, MappedColumn


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: MappedColumn[datetime] = sa.orm.mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: MappedColumn[datetime] = sa.orm.mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
