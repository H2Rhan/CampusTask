from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class TaskStatus(str, enum.Enum):
    """任务状态机（见 docs/ARCHITECTURE.md 状态机图）。"""

    PENDING = "PENDING"                  # 待接单
    ACCEPTED = "ACCEPTED"                # 已接单
    IN_PROGRESS = "IN_PROGRESS"          # 进行中
    ARRIVED_PICKUP = "ARRIVED_PICKUP"    # 已到达取件点
    PICKED_UP = "PICKED_UP"              # 已取件
    DELIVERING = "DELIVERING"            # 配送中
    PENDING_CONFIRM = "PENDING_CONFIRM"  # 待验收
    COMPLETED = "COMPLETED"              # 已完成
    SETTLED = "SETTLED"                  # 已结算
    CANCELLED = "CANCELLED"              # 已取消
    ARBITRATING = "ARBITRATING"          # 仲裁中
    CLOSED_BY_ARBITRATION = "CLOSED_BY_ARBITRATION"  # 仲裁关闭


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publisher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    accepter_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[str] = mapped_column(String(32), default="其他")

    start_node: Mapped[str] = mapped_column(String(64))       # 校园图节点 id
    end_node: Mapped[str] = mapped_column(String(64))
    start_name: Mapped[str] = mapped_column(String(64))
    end_name: Mapped[str] = mapped_column(String(64))

    reward: Mapped[float] = mapped_column(Float)              # 悬赏金额（元）
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    distance: Mapped[float] = mapped_column(Float, default=0.0)     # 起步→终点最短距离（米）
    est_minutes: Mapped[float] = mapped_column(Float, default=0.0)  # 预计步行分钟

    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.PENDING.value, index=True)
    raw_text: Mapped[str] = mapped_column(Text, default="")   # AI 解析的原始自然语言
    special_requirements: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TaskEvent(Base):
    """任务时间线事件：状态变更、快捷操作、仲裁证据的时间轴来源。"""

    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
