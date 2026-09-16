import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.security import create_access_token, hash_password, verify_password
from ...db.session import get_db
from ...models.user import User
from ...schemas import LoginIn, RegisterIn, TokenOut, UserOut, WechatLoginIn
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


@router.post("/wechat", response_model=TokenOut, summary="微信小程序一键登录（code2session）")
def wechat_login(payload: WechatLoginIn, db: Session = Depends(get_db)):
    """正式环境：用 wx.login 的 code 换 openid，openid 绑定校园账号。
    开发环境（未配置 WX_APPID）：code 传 "dev-{学号}" 直接登录对应账号。
    """
    if not (settings.wx_appid and settings.wx_secret):
        if not payload.code.startswith("dev-"):
            raise HTTPException(400, "开发模式请使用 dev-{学号} 作为 code")
        user = db.query(User).filter(User.student_no == payload.code[4:]).first()
        if user is None:
            raise HTTPException(404, "账号不存在，请先注册")
        return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))

    resp = httpx.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={
            "appid": settings.wx_appid,
            "secret": settings.wx_secret,
            "js_code": payload.code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    data = resp.json()
    openid = data.get("openid")
    if not openid:
        raise HTTPException(401, f"微信登录失败: {data.get('errmsg', 'unknown')}")

    user = db.query(User).filter(User.openid == openid).first()
    if user is None:
        # 首次登录：绑定校园身份后建档
        if not (payload.student_no and payload.name):
            raise HTTPException(428, "首次使用需绑定校园身份（student_no + name）")
        if db.query(User).filter(User.student_no == payload.student_no).first():
            raise HTTPException(409, "该学号已注册，请使用账号密码登录后绑定微信")
        user = User(
            student_no=payload.student_no,
            password_hash=hash_password(f"wx-{openid}"),
            name=payload.name,
            college=payload.college,
            openid=openid,
            credit_score=settings.initial_credit_score,
            is_verified=True,
        )
        db.add(user)
        db.flush()
        wallet_service.get_or_create_wallet(db, user.id)
        db.commit()
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))
