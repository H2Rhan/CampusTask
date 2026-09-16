from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class ArbitrationStatus(str, enum.Enum):
    OPEN = "OPEN"              # 已申请，待平台介入
    REVIEWING = "REVIEWING"    # 证据审核中
    RESOLVED = "RESOLVED"      # 已裁决


class Verdict(str, enum.Enum):
    PUBLISHER_WIN = "PUBLISHER_WIN"  # 悬赏退回发布者
    ACCEPTER_WIN = "ACCEPTER_WIN"    # 悬赏结算给接单者
    SPLIT = "SPLIT"                  # 各半


class Arbitration(Base):
    __tablename__ = "arbitrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    initiator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=ArbitrationStatus.OPEN.value)
    evidence: Mapped[list] = mapped_column(JSON, default=list)  # [{user_id, kind, content, created_at}]
    verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolution: Mapped[str] = mapped_column(Text, default="")
    suggestion: Mapped[str] = mapped_column(Text, default="")   # 规则引擎生成的辅助意见
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
