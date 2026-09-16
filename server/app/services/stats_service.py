"""运营数据看板——三创赛/创新创业赛的数据线。

所有指标直接落库统计，内测期间（ROADMAP W7-W8）每日导出即为参赛材料。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.arbitration import Arbitration
from ..models.task import Task, TaskStatus
from ..models.user import User


def overview(db: Session, days: int = 30) -> dict:
    since = datetime.now() - timedelta(days=days)

    users_total = db.query(func.count(User.id)).scalar() or 0
    new_users = db.query(func.count(User.id)).filter(User.created_at >= since).scalar() or 0

    tasks_total = db.query(func.count(Task.id)).scalar() or 0
    tasks_in_window = db.query(func.count(Task.id)).filter(Task.created_at >= since).scalar() or 0
    completed = db.query(func.count(Task.id)).filter(
        Task.status.in_([TaskStatus.SETTLED.value, TaskStatus.COMPLETED.value, TaskStatus.CLOSED_BY_ARBITRATION.value])
    ).scalar() or 0
    accepted_or_beyond = db.query(func.count(Task.id)).filter(
        Task.status != TaskStatus.PENDING.value, Task.status != TaskStatus.CANCELLED.value
    ).scalar() or 0
    cancelled = db.query(func.count(Task.id)).filter(Task.status == TaskStatus.CANCELLED.value).scalar() or 0

    avg_reward = db.query(func.avg(Task.reward)).scalar() or 0.0
    avg_finish = db.query(func.avg(User.total_finish_minutes / User.tasks_completed)).filter(
        User.tasks_completed > 0
    ).scalar() or 0.0

    # 复购率：窗口内发布 >= 2 次的发布者占比
    publisher_counts = (
        db.query(Task.publisher_id, func.count(Task.id).label("cnt"))
        .filter(Task.created_at >= since)
        .group_by(Task.publisher_id)
        .all()
    )
    publishers = len(publisher_counts)
    repeat_publishers = sum(1 for _, cnt in publisher_counts if cnt >= 2)

    arbitrations = db.query(func.count(Arbitration.id)).scalar() or 0

    def rate(part: float, whole: float) -> float:
        return round(part / whole, 4) if whole else 0.0

    return {
        "window_days": days,
        "users_total": users_total,
        "new_users": new_users,
        "tasks_total": tasks_total,
        "tasks_in_window": tasks_in_window,
        "tasks_completed": completed,
        "tasks_cancelled": cancelled,
        "acceptance_rate": rate(accepted_or_beyond, tasks_total),       # 接单率
        "completion_rate": rate(completed, tasks_total),                 # 完成率
        "arbitration_rate": rate(arbitrations, tasks_total),             # 仲裁率
        "avg_reward": round(avg_reward, 2),                              # 平均悬赏（元）
        "avg_finish_minutes": round(avg_finish, 1),                      # 平均完成时长（分钟）
        "repurchase_rate": rate(repeat_publishers, publishers),          # 复购率
        "publishers_in_window": publishers,
    }
