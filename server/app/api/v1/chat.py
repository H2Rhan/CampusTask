"""任务聊天室：撮合成功后建立，任务结束后归档。

- REST: 拉取历史消息
- WebSocket: /ws/chat/{task_id}?token=... 实时收发
- 快捷操作（quick 消息）直接驱动任务状态机
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ...core.deps import get_current_user, get_ws_user
from ...db.session import SessionLocal, get_db
from ...models.chat import ChatMessage
from ...models.task import Task, TaskStatus
from ...models.user import User
from ...schemas import ChatMessageOut
from ...services import task_service
from ...services.state_machine import QUICK_ACTION_LABELS
from ...services.task_service import TaskError

router = APIRouter(tags=["聊天"])

# task_id -> set[WebSocket]
_rooms: dict[int, set[WebSocket]] = {}

CHAT_ACTIVE_STATES = {
    TaskStatus.ACCEPTED.value,
    TaskStatus.IN_PROGRESS.value,
    TaskStatus.ARRIVED_PICKUP.value,
    TaskStatus.PICKED_UP.value,
    TaskStatus.DELIVERING.value,
    TaskStatus.PENDING_CONFIRM.value,
}


@router.get("/tasks/{task_id}/messages", response_model=list[ChatMessageOut], summary="聊天记录")
def get_messages(task_id: int, limit: int = 100, me: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "任务不存在")
    if me.id not in (task.publisher_id, task.accepter_id):
        raise HTTPException(403, "只有任务双方可以查看聊天")
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.task_id == task_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )[::-1]


async def _broadcast(task_id: int, payload: dict) -> None:
    dead = []
    for ws in _rooms.get(task_id, set()):
        try:
            await ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _rooms[task_id].discard(ws)


@router.websocket("/ws/chat/{task_id}")
async def chat_ws(websocket: WebSocket, task_id: int):
    db: Session = SessionLocal()
    try:
        user = get_ws_user(websocket, db)
        task = db.get(Task, task_id)
        if user is None or task is None or user.id not in (task.publisher_id, task.accepter_id):
            await websocket.close(code=4403)
            return
        await websocket.accept()
        _rooms.setdefault(task_id, set()).add(websocket)
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {"type": "text", "content": raw}

                msg_type = data.get("type", "text")
                content = str(data.get("content", "")).strip()
                if not content:
                    continue

                if msg_type == "quick":
                    # 快捷操作：驱动任务状态机，由系统广播结果
                    action = data.get("action", "")
                    try:
                        task_service.advance(db, task, user, action)
                        db.commit()
                        db.refresh(task)
                        label = QUICK_ACTION_LABELS.get(action, action)
                        msg = ChatMessage(task_id=task_id, sender_id=user.id, msg_type="quick", content=label)
                        db.add(msg)
                        db.commit()
                        await _broadcast(task_id, {
                            "type": "quick", "sender_id": user.id, "content": label,
                            "task_status": task.status, "id": msg.id,
                        })
                    except TaskError as e:
                        db.rollback()
                        await websocket.send_text(json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False))
                else:
                    if task.status not in CHAT_ACTIVE_STATES:
                        await websocket.send_text(json.dumps(
                            {"type": "error", "content": "聊天室已归档"}, ensure_ascii=False))
                        continue
                    msg = ChatMessage(task_id=task_id, sender_id=user.id, msg_type="text", content=content[:1000])
                    db.add(msg)
                    db.commit()
                    await _broadcast(task_id, {
                        "type": "text", "sender_id": user.id, "content": msg.content, "id": msg.id,
                    })
        except WebSocketDisconnect:
            pass
        finally:
            _rooms.get(task_id, set()).discard(websocket)
    finally:
        db.close()
