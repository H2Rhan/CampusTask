"""校园信用体系：信用分驱动任务推荐与接单权限。

规则（v1）：
- 完成一单：+1，上限 120
- 好评（>=4 星）：额外 +0.5
- 差评（<=2 星）：-3
- 主动取消已接任务：-5
- 仲裁败诉：-10
- 信用分 < 60：限制接高价值任务（>= 20 元）
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.user import User

CREDIT_MAX = 120.0
CREDIT_MIN = 0.0
HIGH_VALUE_THRESHOLD = 20.0
LOW_CREDIT_LINE = 60.0


def _clamp(score: float) -> float:
    return max(CREDIT_MIN, min(CREDIT_MAX, score))


def apply_completion(db: Session, user: User, finish_minutes: float) -> None:
    user.tasks_completed += 1
    user.total_finish_minutes += max(finish_minutes, 0.0)
    user.credit_score = _clamp(user.credit_score + 1.0)


def apply_cancellation(db: Session, user: User) -> None:
    user.tasks_cancelled += 1
    user.credit_score = _clamp(user.credit_score - 5.0)


def apply_review(db: Session, reviewee: User, rating: int) -> None:
    reviewee.total_reviews += 1
    if rating >= 4:
        reviewee.good_reviews += 1
        reviewee.credit_score = _clamp(reviewee.credit_score + 0.5)
    elif rating <= 2:
        reviewee.credit_score = _clamp(reviewee.credit_score - 3.0)


def apply_arbitration_loss(db: Session, user: User) -> None:
    user.complaints += 1
    user.credit_score = _clamp(user.credit_score - 10.0)


def can_accept(user: User, reward: float) -> tuple[bool, str]:
    """接单权限校验。返回 (allowed, reason)。"""
    if reward >= HIGH_VALUE_THRESHOLD and user.credit_score < LOW_CREDIT_LINE:
        return False, f"信用分 {user.credit_score:.0f} 低于 {LOW_CREDIT_LINE:.0f}，暂不能接 {HIGH_VALUE_THRESHOLD:.0f} 元以上高价值任务"
    return True, ""
