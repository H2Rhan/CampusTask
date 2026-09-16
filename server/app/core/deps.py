"""FastAPI dependencies: current user (JWT Bearer)."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, WebSocket, status
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..models.user import User
from .security import decode_access_token


def get_current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> User:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少或非法的 Authorization 头")
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录状态无效或已过期")
    return user


def get_ws_user(websocket: WebSocket, db: Session) -> User | None:
    """WebSocket 场景从 query string 取 token。"""
    token = websocket.query_params.get("token", "")
    user_id = decode_access_token(token) if token else None
    return db.get(User, user_id) if user_id else None
