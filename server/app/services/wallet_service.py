"""虚拟钱包：发布冻结 → 完成结算 → 仲裁退回 的可信资金流。

比赛 Demo 使用虚拟钱包；正式上线时本模块对接微信支付/持牌支付机构，
平台不做资金托管（见 docs/PRD.md 支付合规说明）。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.wallet import TxKind, Wallet, WalletTransaction


class WalletError(Exception):
    pass


def get_or_create_wallet(db: Session, user_id: int) -> Wallet:
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
    if wallet is None:
        wallet = Wallet(user_id=user_id, balance=0.0, frozen=0.0)
        db.add(wallet)
        db.flush()
    return wallet


def _record(db: Session, wallet: Wallet, kind: TxKind, amount: float, task_id: int | None, remark: str) -> WalletTransaction:
    tx = WalletTransaction(
        user_id=wallet.user_id,
        task_id=task_id,
        kind=kind.value,
        amount=round(amount, 2),
        balance_after=round(wallet.balance, 2),
        frozen_after=round(wallet.frozen, 2),
        remark=remark,
    )
    db.add(tx)
    return tx


def recharge(db: Session, user_id: int, amount: float) -> Wallet:
    if amount <= 0:
        raise WalletError("充值金额必须大于 0")
    wallet = get_or_create_wallet(db, user_id)
    wallet.balance += amount
    _record(db, wallet, TxKind.RECHARGE, amount, None, "钱包充值")
    db.flush()
    return wallet


def freeze(db: Session, user_id: int, amount: float, task_id: int) -> Wallet:
    """发布任务：余额 → 冻结。"""
    wallet = get_or_create_wallet(db, user_id)
    if amount <= 0:
        raise WalletError("悬赏金额必须大于 0")
    if wallet.balance < amount:
        raise WalletError("余额不足，请先充值")
    wallet.balance -= amount
    wallet.frozen += amount
    _record(db, wallet, TxKind.FREEZE, -amount, task_id, f"发布任务 #{task_id} 冻结悬赏")
    db.flush()
    return wallet


def unfreeze(db: Session, user_id: int, amount: float, task_id: int, remark: str = "") -> Wallet:
    """取消任务 / 仲裁判发布者胜诉：冻结 → 余额。"""
    wallet = get_or_create_wallet(db, user_id)
    if wallet.frozen < amount:
        raise WalletError("冻结金额不足")
    wallet.frozen -= amount
    wallet.balance += amount
    _record(db, wallet, TxKind.UNFREEZE, amount, task_id, remark or f"任务 #{task_id} 解冻退回")
    db.flush()
    return wallet


def settle(db: Session, publisher_id: int, accepter_id: int, amount: float, task_id: int) -> None:
    """任务验收：发布者冻结资金划出，接单者入账（扣除平台服务费）。"""
    pub = get_or_create_wallet(db, publisher_id)
    if pub.frozen < amount:
        raise WalletError("发布者冻结金额不足，无法结算")
    fee = round(amount * settings.platform_fee_rate, 2)
    income = round(amount - fee, 2)

    pub.frozen -= amount
    _record(db, pub, TxKind.SETTLE_OUT, -amount, task_id, f"任务 #{task_id} 验收结算")

    acc = get_or_create_wallet(db, accepter_id)
    acc.balance += income
    _record(db, acc, TxKind.SETTLE_IN, income, task_id, f"任务 #{task_id} 收入（悬赏 {amount} 元）")
    if fee > 0:
        _record(db, acc, TxKind.PLATFORM_FEE, -fee, task_id, f"平台撮合服务费 {settings.platform_fee_rate:.0%}")
    db.flush()
