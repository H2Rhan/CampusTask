from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.deps import get_current_user
from ...db.session import get_db
from ...models.task import Task, TaskStatus
from ...models.user import User, UserRoute
from ...schemas import BatchAssignmentItem, BatchAssignOut
from ...services import assignment_service, stats_service

router = APIRouter(tags=["运营数据与批量调度"])

ADMIN_STUDENT_NOS = {"admin", "20260001"}


@router.get("/stats/overview", summary="运营数据看板（注册/完成率/均时/复购/仲裁率）")
def stats_overview(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    # 演示阶段放开给前端看板；正式环境应加管理员鉴权
    return stats_service.overview(db, days)


@router.get("/match/batch-assign", response_model=BatchAssignOut,
            summary="批量任务分配：全校总边际成本最小化（匈牙利算法）")
def batch_assign(db: Session = Depends(get_db)):
    open_tasks = db.query(Task).filter(Task.status == TaskStatus.PENDING.value).all()
    routes = db.query(UserRoute).filter(UserRoute.active.is_(True)).all()
    candidates = []
    for r in routes:
        user = db.get(User, r.user_id)
        if user is not None:
            candidates.append((user, r.waypoints))
    result = assignment_service.batch_assign(open_tasks, candidates)
    return BatchAssignOut(
        assignments=[BatchAssignmentItem(**a.__dict__) for a in result.assignments],
        total_marginal_distance=result.total_marginal_distance,
        total_marginal_minutes=result.total_marginal_minutes,
        unassigned_task_ids=result.unassigned_task_ids,
    )
