"""Sprint 12 — DialToken (拨号扫码备份方案).

物业管理员/坐席在前端「扫码拨号」生成的一次性 token：
- 前端调 dial-request mode=qr 时插入一行
- 坐席 App 扫码后调 dial-info?token=xxx 消费（first-write-wins 防重放）
- 10 分钟未消费即过期

仅存 SHA256(token)，明文 token 只在响应中给前端，不落库。
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DialToken(Base):
    __tablename__ = "dial_token"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    call_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("call_record.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("tenant.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        sa.String(64), unique=True, nullable=False
    )  # SHA256 hex
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (sa.Index("ix_dial_token_used", "token_hash", "used_at"),)
