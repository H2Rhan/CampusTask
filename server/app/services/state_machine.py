"""任务状态机：所有状态变更必须经由本模块校验，禁止越级跳转。"""
from __future__ import annotations

from ..models.task import TaskStatus

# 允许的状态迁移表：from -> {to: actor}
# actor: publisher=发布者 accepter=接单者 either=双方 system/admin=平台
TRANSITIONS: dict[TaskStatus, dict[TaskStatus, str]] = {
    TaskStatus.PENDING: {
        TaskStatus.ACCEPTED: "accepter",
        TaskStatus.CANCELLED: "publisher",
    },
    TaskStatus.ACCEPTED: {
        TaskStatus.IN_PROGRESS: "accepter",
        TaskStatus.CANCELLED: "either",
        TaskStatus.ARBITRATING: "either",
    },
    TaskStatus.IN_PROGRESS: {
        TaskStatus.ARRIVED_PICKUP: "accepter",
        TaskStatus.CANCELLED: "either",
        TaskStatus.ARBITRATING: "either",
    },
    TaskStatus.ARRIVED_PICKUP: {
        TaskStatus.PICKED_UP: "accepter",
        TaskStatus.ARBITRATING: "either",
    },
    TaskStatus.PICKED_UP: {
        TaskStatus.DELIVERING: "accepter",
        TaskStatus.ARBITRATING: "either",
    },
    TaskStatus.DELIVERING: {
        TaskStatus.PENDING_CONFIRM: "accepter",
        TaskStatus.ARBITRATING: "either",
    },
    TaskStatus.PENDING_CONFIRM: {
        TaskStatus.COMPLETED: "publisher",
        TaskStatus.ARBITRATING: "publisher",
    },
    TaskStatus.COMPLETED: {
        TaskStatus.SETTLED: "system",
    },
    TaskStatus.ARBITRATING: {
        TaskStatus.CLOSED_BY_ARBITRATION: "admin",
    },
}

# 快捷操作 → 目标状态
QUICK_ACTIONS: dict[str, TaskStatus] = {
    "start": TaskStatus.IN_PROGRESS,
    "arrive_pickup": TaskStatus.ARRIVED_PICKUP,
    "pickup": TaskStatus.PICKED_UP,
    "deliver": TaskStatus.DELIVERING,
    "finish": TaskStatus.PENDING_CONFIRM,
}

QUICK_ACTION_LABELS = {
    "start": "🚶 开始执行任务",
    "arrive_pickup": "📍 我已到达取件点",
    "pickup": "📦 已取到物品",
    "deliver": "🚚 正在前往目的地",
    "finish": "✅ 已送达，请验收",
}


class IllegalTransition(Exception):
    pass


def can_transition(frm: TaskStatus, to: TaskStatus) -> bool:
    return to in TRANSITIONS.get(frm, {})


def required_actor(frm: TaskStatus, to: TaskStatus) -> str:
    return TRANSITIONS[frm][to]


def assert_transition(frm: TaskStatus, to: TaskStatus) -> None:
    if not can_transition(frm, to):
        raise IllegalTransition(f"非法状态迁移: {frm.value} -> {to.value}")
