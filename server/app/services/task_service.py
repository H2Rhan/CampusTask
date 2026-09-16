"""任务生命周期服务：创建（冻结悬赏）→ 接单 → 执行 → 验收 → 结算 / 取消。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..campus_map.graph import get_campus_graph
from ..campus_map.routing import dijkstra
from ..models.chat import ChatMessage
from ..models.task import Task, TaskEvent, TaskStatus
from ..models.user import User
from . import credit_service, wallet_service
from .state_machine import IllegalTransition, QUICK_ACTIONS, assert_transition, required_actor


class TaskError(Exception):
    pass


def _event(db: Session, task_id: int, actor_id: int | None, event: str, detail: str = "") -> None:
    db.add(TaskEvent(task_id=task_id, actor_id=actor_id, event=event, detail=detail))


def _system_message(db: Session, task_id: int, content: str) -> None:
    db.add(ChatMessage(task_id=task_id, sender_id=None, msg_type="system", content=content))


def create_task(
    db: Session,
    publisher: User,
    *,
    title: str,
    description: str = "",
    task_type: str = "其他",
    start_node: str,
    end_node: str,
    reward: float,
    deadline: datetime | None = None,
    raw_text: str = "",
    special_requirements: str = "",
) -> Task:
    graph = get_campus_graph()
    if start_node not in graph.nodes or end_node not in graph.nodes:
        raise TaskError("起点或终点不在校园地图中")
    if start_node == end_node:
        raise TaskError("起点和终点不能相同")
    if reward <= 0:
        raise TaskError("悬赏金额必须大于 0")

    route = dijkstra(graph, start_node, end_node)
    if route is None:
        raise TaskError("起点与终点之间不可达")

    task = Task(
        publisher_id=publisher.id,
        title=title,
        description=description,
        task_type=task_type,
        start_node=start_node,
        end_node=end_node,
        start_name=graph.node_name(start_node),
        end_name=graph.node_name(end_node),
        reward=reward,
        deadline=deadline,
        distance=route.distance,
        est_minutes=route.minutes,
        raw_text=raw_text,
        special_requirements=special_requirements,
        status=TaskStatus.PENDING.value,
    )
    db.add(task)
    db.flush()  # 获得 task.id

    wallet_service.freeze(db, publisher.id, reward, task.id)
    _event(db, task.id, publisher.id, "TASK_CREATED", f"发布任务，冻结悬赏 {reward} 元")
    return task


def get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise TaskError("任务不存在")
    return task


def accept_task(db: Session, task: Task, accepter: User) -> Task:
    status = TaskStatus(task.status)
    if status != TaskStatus.PENDING:
        raise TaskError("任务已被接取或已关闭")
    if task.publisher_id == accepter.id:
        raise TaskError("不能接取自己发布的任务")
    allowed, reason = credit_service.can_accept(accepter, task.reward)
    if not allowed:
        raise TaskError(reason)

    assert_transition(status, TaskStatus.ACCEPTED)
    task.accepter_id = accepter.id
    task.status = TaskStatus.ACCEPTED.value
    task.accepted_at = datetime.now()
    _event(db, task.id, accepter.id, "TASK_ACCEPTED", f"{accepter.name} 接单")
    _system_message(db, task.id, f"任务已被 {accepter.name} 接取，聊天室已建立")
    db.flush()
    return task


def _check_actor(task: Task, user: User, actor: str) -> None:
    if actor == "publisher" and task.publisher_id != user.id:
        raise TaskError("只有发布者可以执行此操作")
    if actor == "accepter" and task.accepter_id != user.id:
        raise TaskError("只有接单者可以执行此操作")
    if actor == "either" and user.id not in (task.publisher_id, task.accepter_id):
        raise TaskError("只有任务双方可以执行此操作")


def advance(db: Session, task: Task, actor: User, action: str) -> Task:
    """快捷操作驱动状态机前进（仅接单者）。返回更新后的任务。"""
    if action not in QUICK_ACTIONS:
        raise TaskError(f"未知操作: {action}")
    target = QUICK_ACTIONS[action]
    status = TaskStatus(task.status)
    try:
        assert_transition(status, target)
    except IllegalTransition as e:
        raise TaskError(str(e)) from e
    _check_actor(task, actor, required_actor(status, target))

    task.status = target.value
    _event(db, task.id, actor.id, f"STATE_{target.value}", f"快捷操作: {action}")
    _system_message(db, task.id, f"任务状态更新：{target.value}")
    db.flush()
    return task


def confirm_complete(db: Session, task: Task, publisher: User) -> Task:
    """发布者验收：COMPLETED → 自动结算 → SETTLED。"""
    status = TaskStatus(task.status)
    try:
        assert_transition(status, TaskStatus.COMPLETED)
    except IllegalTransition as e:
        raise TaskError(str(e)) from e
    _check_actor(task, publisher, "publisher")
    if task.accepter_id is None:
        raise TaskError("任务尚未被接取")

    task.status = TaskStatus.COMPLETED.value
    task.completed_at = datetime.now()
    _event(db, task.id, publisher.id, "TASK_COMPLETED", "发布者确认验收")

    wallet_service.settle(db, task.publisher_id, task.accepter_id, task.reward, task.id)
    task.status = TaskStatus.SETTLED.value

    accepter = db.get(User, task.accepter_id)
    if accepter is not None and task.accepted_at is not None:
        minutes = (task.completed_at - task.accepted_at).total_seconds() / 60
        credit_service.apply_completion(db, accepter, minutes)

    _event(db, task.id, None, "TASK_SETTLED", f"悬赏 {task.reward} 元已结算")
    _system_message(db, task.id, "任务已完成并自动结算，聊天室已归档")
    db.flush()
    return task


def cancel(db: Session, task: Task, actor: User) -> Task:
    status = TaskStatus(task.status)
    try:
        assert_transition(status, TaskStatus.CANCELLED)
    except IllegalTransition as e:
        raise TaskError(f"当前状态（{status.value}）不可取消") from e
    _check_actor(task, actor, required_actor(status, TaskStatus.CANCELLED))

    # 接单者中途取消 → 信用惩罚
    if status != TaskStatus.PENDING and actor.id == task.accepter_id:
        credit_service.apply_cancellation(db, actor)

    wallet_service.unfreeze(db, task.publisher_id, task.reward, task.id, remark=f"任务 #{task.id} 取消，悬赏退回")
    task.status = TaskStatus.CANCELLED.value
    _event(db, task.id, actor.id, "TASK_CANCELLED", "任务取消，悬赏退回发布者")
    _system_message(db, task.id, "任务已取消")
    db.flush()
    return task
