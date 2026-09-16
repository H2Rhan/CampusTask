from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.security import create_access_token, hash_password, verify_password
from ...db.session import get_db
from ...models.user import User
from ...schemas import LoginIn, RegisterIn, TokenOut, UserOut
from ...services import wallet_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=TokenOut, summary="校园用户注册")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.student_no == payload.student_no).first():
        raise HTTPException(409, "该学号已注册")
    user = User(
        student_no=payload.student_no,
        password_hash=hash_password(payload.password),
        name=payload.name,
        college=payload.college,
        grade=payload.grade,
        phone=payload.phone,
        dorm_area=payload.dorm_area,
        credit_score=settings.initial_credit_score,
        is_verified=True,  # MVP：默认通过校园认证；正式版接入学校统一身份认证
    )
    db.add(user)
    db.flush()
    wallet_service.get_or_create_wallet(db, user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut, summary="登录")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.student_no == payload.student_no).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "学号或密码错误")
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))
