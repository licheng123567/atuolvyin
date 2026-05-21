"""v2.1 — 设备录音能力探测留痕 (PRD § 8.4)。

每次自检写一行；用于：
  - PC 管理员看坐席设备健康度
  - 静态矩阵判定与运行时实测的差异审计（积累后回头调整矩阵）
  - 合同纠纷时拿数据证明该坐席设备不支持

字段 source 区分：
  - static_matrix: 来自客户端上报的 ROM/Android 走静态矩阵推断
  - runtime_verified: RecordingScanner 实测（找到 / 找不到文件）覆盖矩阵
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class DeviceCapabilityLog(Base):
    __tablename__ = "device_capability_log"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    manufacturer: Mapped[str | None] = mapped_column(sa.String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    android_version: Mapped[str | None] = mapped_column(sa.String(16), nullable=True)
    # 如 "AOSP on Google Pixel 8 (Android 14)" — derive_rom_label 输出
    rom_label: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    # realtime / post_upload / incompatible
    capability: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    actual_recording_works: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    # static_matrix / runtime_verified
    source: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.Index(
            "ix_device_capability_log_tenant_user_time",
            "tenant_id",
            "user_id",
            "detected_at",
        ),
        sa.Index("ix_device_capability_log_device", "device_id"),
        sa.CheckConstraint(
            "capability IN ('realtime','post_upload','incompatible')",
            name="ck_device_capability_log_capability",
        ),
        sa.CheckConstraint(
            "source IN ('static_matrix','runtime_verified')",
            name="ck_device_capability_log_source",
        ),
    )
