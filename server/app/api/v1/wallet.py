from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...db.session import get_db
from ...models.user import User
from ...models.wallet import WalletTransaction
from ...schemas import RechargeIn, TransactionOut, WalletOut
from ...services import wallet_service
from ...services.wallet_service import WalletError

router = APIRouter(prefix="/wallet", tags=["虚拟钱包"])


@router.get("/me", response_model=WalletOut, summary="我的钱包")
def my_wallet(me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wallet = wallet_service.get_or_create_wallet(db, me.id)
    db.commit()
    return WalletOut(balance=round(wallet.balance, 2), frozen=round(wallet.frozen, 2))


@router.post("/recharge", response_model=WalletOut, summary="充值（Demo 虚拟充值）")
def recharge(payload: RechargeIn, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        wallet = wallet_service.recharge(db, me.id, payload.amount)
        db.commit()
        return WalletOut(balance=round(wallet.balance, 2), frozen=round(wallet.frozen, 2))
    except WalletError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("/transactions", response_model=list[TransactionOut], summary="资金流水")
def transactions(limit: int = Query(default=50, le=200), me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(WalletTransaction)
        .filter(WalletTransaction.user_id == me.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
