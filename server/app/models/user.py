from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    name: Mapped[str] = mapped_column(String(64))
    school: Mapped[str] = mapped_column(String(64), default="南开大学")
    college: Mapped[str] = mapped_column(String(64), default="")
    grade: Mapped[str] = mapped_column(String(16), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    openid: Mapped[str] = mapped_column(String(64), default="")  # 微信 OpenID（小程序登录后绑定）
    dorm_area: Mapped[str] = mapped_column(String(64), default="")
    is_verified: Mapped[bool] = mapped_column(default=False)     # 校园身份认证

    # ---- 信用体系 ----
    credit_score: Mapped[float] = mapped_column(Float, default=100.0)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    tasks_cancelled: Mapped[int] = mapped_column(Integer, default=0)
    complaints: Mapped[int] = mapped_column(Integer, default=0)
    good_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_finish_minutes: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    routes: Mapped[list["UserRoute"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def good_rate(self) -> float:
        return round(self.good_reviews / self.total_reviews, 4) if self.total_reviews else 1.0

    @property
    def avg_finish_minutes(self) -> float:
        return round(self.total_finish_minutes / self.tasks_completed, 1) if self.tasks_completed else 0.0


class UserRoute(Base):
    """用户的日常路线（如 宿舍→图书馆→食堂），智能匹配的输入之一。"""

    __tablename__ = "user_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64), default="日常路线")
    waypoints: Mapped[list] = mapped_column(JSON)  # ["dorm_16", "canteen_2", "teach_b"]
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="routes")
