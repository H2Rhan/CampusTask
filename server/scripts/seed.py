"""演示数据种子：3 名学生 + 日常路线 + 1 个管理员。

运行：python -m scripts.seed（在 server/ 目录下）
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.models.user import User, UserRoute  # noqa: E402
from app.services import wallet_service  # noqa: E402

DEMO_USERS = [
    # 学号, 姓名, 学院, 宿舍, 日常路线
    ("20260001", "平台管理员", "计算机学院", "宿舍1斋", ["dorm_1", "canteen_1", "library"]),
    ("20261111", "韩浩然", "计算机学院", "宿舍16斋", ["dorm_16", "canteen_2", "teach_b", "library"]),
    ("20262222", "张同学", "软件学院", "宿舍16斋", ["dorm_16", "library", "canteen_2", "stadium"]),
    ("20263333", "李同学", "金融学院", "中海国际宿舍区", ["zhonghai", "gate_west", "canteen_1", "teach_a"]),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        for student_no, name, college, dorm, waypoints in DEMO_USERS:
            if db.query(User).filter(User.student_no == student_no).first():
                continue
            user = User(
                student_no=student_no,
                password_hash=hash_password("campustask-demo"),
                name=name,
                college=college,
                grade="2025级",
                dorm_area=dorm,
                is_verified=True,
                credit_score=100.0,
            )
            db.add(user)
            db.flush()
            wallet_service.get_or_create_wallet(db, user.id)
            wallet_service.recharge(db, user.id, 50.0)
            db.add(UserRoute(user_id=user.id, name="日常路线", waypoints=waypoints))
        db.commit()
        print("演示数据已就绪：4 个账号（密码均为 campustask-demo），每人预存 50 元。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
