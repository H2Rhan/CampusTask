from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...campus_map.graph import get_campus_graph
from ...core.deps import get_current_user
from ...db.session import get_db
from ...models.review import Review
from ...models.task import Task, TaskEvent, TaskStatus
from ...models.user import User
from ...schemas import (
    ReviewIn,
    TaskActionIn,
    TaskCreateIn,
    TaskEventOut,
    TaskOut,
)
from ...services import credit_service, task_service
from ...services.task_service import TaskError

router = APIRouter(prefix="/tasks", tags=["任务"])


def _400(e: Exception):
    raise HTTPException(400, str(e))


@router.post("", response_model=TaskOut, summary="发布任务（自动冻结悬赏）")
def create_task(payload: TaskCreateIn, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    graph = get_campus_graph()
    start, end = graph.resolve(payload.start), graph.resolve(payload.destination)
    if start is None or end is None:
        raise HTTPException(400, "起点或终点无法识别，请使用校园地图中的地点")
    title = payload.title or f"{graph.node_name(start)} → {graph.node_name(end)}"
    try:
        task = task_service.create_task(
            db, me,
            title=title, description=payload.description, task_type=payload.task_type,
            start_node=start, end_node=end, reward=payload.reward, deadline=payload.deadline,
            raw_text=payload.raw_text, special_requirements=payload.special_requirements,
        )
        db.commit()
    except (TaskError, Exception) as e:
        db.rollback()
        _400(e)
    return task


@router.get("", response_model=list[TaskOut], summary="任务大厅（附近任务）")
def list_tasks(
    status: str = Query(default="PENDING"),
    task_type: str | None = None,
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Task)
    if status != "ALL":
        q = q.filter(Task.status == status)
    if task_type:
        q = q.filter(Task.task_type == task_type)
    return q.order_by(Task.created_at.desc()).limit(limit).all()


@router.get("/mine", response_model=list[TaskOut], summary="我发布/接取的任务")
def list_mine(
    role: str = Query(default="all", pattern="^(all|publisher|accepter)$"),
    me: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Task)
    if role == "publisher":
        q = q.filter(Task.publisher_id == me.id)
    elif role == "accepter":
        q = q.filter(Task.accepter_id == me.id)
    else:
        q = q.filter((Task.publisher_id == me.id) | (Task.accepter_id == me.id))
    return q.order_by(Task.created_at.desc()).limit(100).all()


@router.get("/{task_id}", response_model=TaskOut, summary="任务详情")
def get_task(task_id: int, db: Session = Depends(get_db)):
    try:
        return task_service.get_task(db, task_id)
    except TaskError as e:
        raise HTTPException(404, str(e))


@router.get("/{task_id}/events", response_model=list[TaskEventOut], summary="任务时间线")
def get_events(task_id: int, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task(db, task_id)
    if me.id not in (task.publisher_id, task.accepter_id):
        raise HTTPException(403, "只有任务双方可以查看时间线")
    return db.query(TaskEvent).filter(TaskEvent.task_id == task_id).order_by(TaskEvent.created_at).all()


@router.post("/{task_id}/accept", response_model=TaskOut, summary="接单")
def accept_task(task_id: int, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        task = task_service.accept_task(db, task_service.get_task(db, task_id), me)
        db.commit()
        return task
    except TaskError as e:
        db.rollback()
        _400(e)


@router.post("/{task_id}/advance", response_model=TaskOut, summary="快捷操作推进任务状态")
def advance_task(task_id: int, payload: TaskActionIn, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        task = task_service.advance(db, task_service.get_task(db, task_id), me, payload.action)
        db.commit()
        return task
    except TaskError as e:
        db.rollback()
        _400(e)


@router.post("/{task_id}/confirm", response_model=TaskOut, summary="发布者验收（自动结算）")
def confirm_task(task_id: int, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        task = task_service.confirm_complete(db, task_service.get_task(db, task_id), me)
        db.commit()
        return task
    except TaskError as e:
        db.rollback()
        _400(e)


@router.post("/{task_id}/cancel", response_model=TaskOut, summary="取消任务（悬赏退回）")
def cancel_task(task_id: int, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        task = task_service.cancel(db, task_service.get_task(db, task_id), me)
        db.commit()
        return task
    except TaskError as e:
        db.rollback()
        _400(e)


@router.post("/{task_id}/review", summary="任务完成后互评")
def review_task(task_id: int, payload: ReviewIn, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task(db, task_id)
    if task.status not in (TaskStatus.COMPLETED.value, TaskStatus.SETTLED.value, TaskStatus.CLOSED_BY_ARBITRATION.value):
        raise HTTPException(400, "任务尚未完成，不能评价")
    if me.id not in (task.publisher_id, task.accepter_id):
        raise HTTPException(403, "只有任务双方可以评价")
    reviewee_id = task.accepter_id if me.id == task.publisher_id else task.publisher_id
    if reviewee_id is None:
        raise HTTPException(400, "任务无对方用户")
    if db.query(Review).filter(Review.task_id == task_id, Review.reviewer_id == me.id).first():
        raise HTTPException(409, "已评价过该任务")

    review = Review(task_id=task_id, reviewer_id=me.id, reviewee_id=reviewee_id, rating=payload.rating, comment=payload.comment)
    db.add(review)
    reviewee = db.get(User, reviewee_id)
    credit_service.apply_review(db, reviewee, payload.rating)
    db.commit()
    return {"ok": True}
