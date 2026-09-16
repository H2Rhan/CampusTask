from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...db.session import get_db
from ...models.arbitration import Arbitration
from ...models.user import User
from ...schemas import (
    ArbitrationOpenIn,
    ArbitrationOut,
    ArbitrationResolveIn,
    EvidenceIn,
)
from ...services import arbitration_service, task_service
from ...services.arbitration_service import ArbitrationError

router = APIRouter(tags=["仲裁"])

# MVP 管理员名单（正式版改为角色表）；首批平台运营账号学号
ADMIN_STUDENT_NOS = {"admin", "20260001"}


def _is_admin(user: User) -> bool:
    return user.student_no in ADMIN_STUDENT_NOS


@router.post("/tasks/{task_id}/arbitrate", response_model=ArbitrationOut, summary="发起仲裁（冻结资金，平台介入）")
def open_arbitration(task_id: int, payload: ArbitrationOpenIn, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        task = task_service.get_task(db, task_id)
        arb = arbitration_service.open_arbitration(db, task, me, payload.reason)
        db.commit()
        return arb
    except (ArbitrationError, Exception) as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.get("/arbitrations/{arb_id}", response_model=ArbitrationOut, summary="仲裁详情")
def get_arbitration(arb_id: int, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    arb = db.get(Arbitration, arb_id)
    if arb is None:
        raise HTTPException(404, "仲裁不存在")
    return arb


@router.get("/arbitrations/{arb_id}/timeline", summary="证据时间线（事件 + 聊天）")
def get_timeline(arb_id: int, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    arb = db.get(Arbitration, arb_id)
    if arb is None:
        raise HTTPException(404, "仲裁不存在")
    return {"timeline": arbitration_service.build_timeline(db, arb.task_id)}


@router.post("/arbitrations/{arb_id}/evidence", response_model=ArbitrationOut, summary="提交证据")
def submit_evidence(arb_id: int, payload: EvidenceIn, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    arb = db.get(Arbitration, arb_id)
    if arb is None:
        raise HTTPException(404, "仲裁不存在")
    try:
        arb = arbitration_service.add_evidence(db, arb, me, payload.kind, payload.content)
        db.commit()
        return arb
    except ArbitrationError as e:
        db.rollback()
        raise HTTPException(400, str(e))


@router.post("/arbitrations/{arb_id}/resolve", response_model=ArbitrationOut, summary="管理员裁决")
def resolve_arbitration(arb_id: int, payload: ArbitrationResolveIn, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _is_admin(me):
        raise HTTPException(403, "只有平台管理员可以裁决")
    arb = db.get(Arbitration, arb_id)
    if arb is None:
        raise HTTPException(404, "仲裁不存在")
    try:
        arb = arbitration_service.resolve(db, arb, payload.verdict, payload.resolution)
        db.commit()
        return arb
    except (ArbitrationError, Exception) as e:
        db.rollback()
        raise HTTPException(400, str(e))
