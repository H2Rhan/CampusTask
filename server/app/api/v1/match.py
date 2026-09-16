from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...campus_map.graph import get_campus_graph
from ...core.deps import get_current_user
from ...db.session import get_db
from ...models.task import Task, TaskStatus
from ...models.user import User, UserRoute
from ...schemas import MatchCandidateOut, TaskOut
from ...services import matching_service
from ...services.credit_service import can_accept

router = APIRouter(prefix="/match", tags=["智能匹配"])


@router.get("/tasks/{task_id}/candidates", response_model=list[MatchCandidateOut],
            summary="为任务寻找最合适的接单者（边际成本排序）")
def match_candidates(task_id: int, limit: int = 10, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")

    routes = db.query(UserRoute).filter(UserRoute.active.is_(True)).all()
    candidates: list[tuple[User, list[str]]] = []
    for r in routes:
        if r.user_id == task.publisher_id:
            continue
        user = db.get(User, r.user_id)
        if user is not None:
            candidates.append((user, r.waypoints))

    results = matching_service.rank_candidates(task, candidates, limit=limit)
    return [MatchCandidateOut(**r.__dict__) for r in results]


@router.get("/for-me", response_model=list[TaskOut],
            summary="为我推荐任务（基于我的日常路线，任务找人）")
def recommend_for_me(limit: int = 20, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    routes = db.query(UserRoute).filter(UserRoute.user_id == me.id, UserRoute.active.is_(True)).all()
    if not routes:
        raise HTTPException(400, "请先登记你的日常路线（POST /users/me/routes）")

    open_tasks = db.query(Task).filter(
        Task.status == TaskStatus.PENDING.value,
        Task.publisher_id != me.id,
    ).order_by(Task.created_at.desc()).limit(200).all()

    graph = get_campus_graph()
    scored: list[tuple[int, str, Task]] = []
    for task in open_tasks:
        allowed, _ = can_accept(me, task.reward)
        if not allowed:
            continue
        best = None
        for r in routes:
            result = matching_service.score_candidate(graph, task, me, r.waypoints)
            if result and (best is None or result.match_percent > best.match_percent):
                best = result
        if best is not None:
            scored.append((best.match_percent, best.reason, task))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[TaskOut] = []
    for percent, reason, task in scored[:limit]:
        dto = TaskOut.model_validate(task)
        dto.match_percent = percent
        dto.match_reason = reason
        out.append(dto)
    return out
