from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.session import Base


class TxKind(str, enum.Enum):
    RECHARGE = "RECHARGE"          # 充值
    FREEZE = "FREEZE"              # 发布任务冻结悬赏
    UNFREEZE = "UNFREEZE"          # 取消/仲裁退回解冻
    SETTLE_OUT = "SETTLE_OUT"      # 结算支出（发布者冻结资金划出）
    SETTLE_IN = "SETTLE_IN"        # 结算收入（接单者入账）
    PLATFORM_FEE = "PLATFORM_FEE"  # 平台撮合服务费
    PENALTY = "PENALTY"            # 仲裁罚金


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0)   # 可用余额
    frozen: Mapped[float] = mapped_column(Float, default=0.0)    # 冻结金额


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    amount: Mapped[float] = mapped_column(Float)   # 正=入账，负=出账（FREEZE/UNFREEZE 记资金变动口径）
    balance_after: Mapped[float] = mapped_column(Float)
    frozen_after: Mapped[float] = mapped_column(Float)
    remark: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
