"""仲裁系统：规则引擎生成辅助意见 + 管理员人工裁决。

v1 不做 AI 仲裁，但规则引擎会自动整理证据时间线并给出建议，
后续可平滑升级为 AI 辅助仲裁（LLM 总结争议焦点）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..models.arbitration import Arbitration, ArbitrationStatus, Verdict
from ..models.chat import ChatMessage
from ..models.task import Task, TaskEvent, TaskStatus
from ..models.user import User
from . import credit_service, wallet_service
from .state_machine import assert_transition


class ArbitrationError(Exception):
    pass


def open_arbitration(db: Session, task: Task, initiator: User, reason: str) -> Arbitration:
    if initiator.id not in (task.publisher_id, task.accepter_id):
        raise ArbitrationError("只有任务双方可以发起仲裁")
    status = TaskStatus(task.status)
    try:
        assert_transition(status, TaskStatus.ARBITRATING)
    except Exception as e:
        raise ArbitrationError(f"当前状态（{status.value}）不可发起仲裁") from e

    existing = db.query(Arbitration).filter(
        Arbitration.task_id == task.id,
        Arbitration.status != ArbitrationStatus.RESOLVED.value,
    ).first()
    if existing:
        raise ArbitrationError("该任务已有进行中的仲裁")

    task.status = TaskStatus.ARBITRATING.value
    arb = Arbitration(task_id=task.id, initiator_id=initiator.id, reason=reason)
    db.add(arb)
    db.flush()
    db.add(TaskEvent(task_id=task.id, actor_id=initiator.id, event="ARBITRATION_OPENED", detail=reason))
    arb.suggestion = generate_suggestion(db, arb)
    db.flush()
    return arb


def add_evidence(db: Session, arb: Arbitration, user: User, kind: str, content: str) -> Arbitration:
    if arb.status == ArbitrationStatus.RESOLVED.value:
        raise ArbitrationError("仲裁已结案，无法提交证据")
    task = db.get(Task, arb.task_id)
    if user.id not in (task.publisher_id, task.accepter_id):
        raise ArbitrationError("只有任务双方可以提交证据")
    evidence = list(arb.evidence or [])
    evidence.append({
        "user_id": user.id,
        "user_name": user.name,
        "kind": kind,  # text / photo / location / other
        "content": content,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })
    arb.evidence = evidence
    if arb.status == ArbitrationStatus.OPEN.value:
        arb.status = ArbitrationStatus.REVIEWING.value
    arb.suggestion = generate_suggestion(db, arb)
    db.flush()
    return arb


def build_timeline(db: Session, task_id: int) -> list[dict]:
    """汇总任务事件 + 聊天记录为统一时间线，供规则引擎与前端展示。"""
    events = db.query(TaskEvent).filter(TaskEvent.task_id == task_id).order_by(TaskEvent.created_at).all()
    messages = db.query(ChatMessage).filter(ChatMessage.task_id == task_id).order_by(ChatMessage.created_at).all()
    timeline: list[dict] = []
    for e in events:
        timeline.append({"time": e.created_at.isoformat(timespec="seconds"), "source": "event", "actor_id": e.actor_id, "content": f"{e.event}: {e.detail}"})
    for m in messages:
        timeline.append({"time": m.created_at.isoformat(timespec="seconds"), "source": "chat", "actor_id": m.sender_id, "content": m.content})
    timeline.sort(key=lambda x: x["time"])
    return timeline


def generate_suggestion(db: Session, arb: Arbitration) -> str:
    """规则引擎：基于任务时间线给出裁决建议（非最终裁决）。"""
    task = db.get(Task, arb.task_id)
    events = db.query(TaskEvent).filter(TaskEvent.task_id == arb.task_id).all()
    event_names = {e.event for e in events}
    messages = db.query(ChatMessage).filter(ChatMessage.task_id == arb.task_id).all()

    picked = any(n.startswith("STATE_PICKED_UP") for n in event_names)
    delivered = any(n.startswith("STATE_PENDING_CONFIRM") for n in event_names)
    publisher_ack = any(
        m.sender_id == task.publisher_id and ("收到" in m.content or "拿到了" in m.content or "谢谢" in m.content)
        for m in messages
    )

    lines = ["【规则引擎辅助意见】", f"争议原因：{arb.reason}"]
    if delivered and publisher_ack:
        lines += [
            f"系统检测：接单者已完成取件与送达流程，且发布者在聊天中确认收到物品。",
            "建议：支持任务完成，悬赏结算给接单者（ACCEPTER_WIN）。",
        ]
    elif not picked:
        lines += [
            "系统检测：任务从未产生取件记录。",
            "建议：支持任务未履约，悬赏退回发布者（PUBLISHER_WIN）。",
        ]
    elif picked and not delivered:
        lines += [
            "系统检测：物品已取但未完成送达确认。",
            "建议：重点核查配送环节证据（定位/照片/聊天记录），倾向人工裁决或 SPLIT。",
        ]
    else:
        lines += [
            "系统检测：送达流程已完成，但发布者未明确确认收货。",
            "建议：人工审核双方证据后裁决；若无反证，倾向 ACCEPTER_WIN。",
        ]
    lines.append("（本意见由规则引擎自动生成，仅供仲裁员参考，不构成最终裁决。）")
    return "\n".join(lines)


def resolve(db: Session, arb: Arbitration, verdict: str, resolution: str) -> Arbitration:
    """管理员裁决：处理资金 + 信用 + 任务状态。"""
    if arb.status == ArbitrationStatus.RESOLVED.value:
        raise ArbitrationError("仲裁已结案")
    if verdict not in {v.value for v in Verdict}:
        raise ArbitrationError("非法裁决结果")

    task = db.get(Task, arb.task_id)
    arb.verdict = verdict
    arb.resolution = resolution
    arb.status = ArbitrationStatus.RESOLVED.value
    arb.resolved_at = datetime.now()

    publisher = db.get(User, task.publisher_id)
    accepter = db.get(User, task.accepter_id) if task.accepter_id else None

    if verdict == Verdict.PUBLISHER_WIN.value:
        wallet_service.unfreeze(db, task.publisher_id, task.reward, task.id, remark=f"仲裁 #{arb.id}：悬赏退回发布者")
        if accepter:
            credit_service.apply_arbitration_loss(db, accepter)
    elif verdict == Verdict.ACCEPTER_WIN.value:
        if accepter is None:
            raise ArbitrationError("任务无接单者，无法判接单者胜诉")
        wallet_service.settle(db, task.publisher_id, task.accepter_id, task.reward, task.id)
        credit_service.apply_arbitration_loss(db, publisher)
    else:  # SPLIT
        half = round(task.reward / 2, 2)
        wallet_service.unfreeze(db, task.publisher_id, half, task.id, remark=f"仲裁 #{arb.id}：一半退回发布者")
        if accepter is not None:
            # 另一半从冻结中结算给接单者
            wallet_service.settle(db, task.publisher_id, task.accepter_id, task.reward - half, task.id)

    task.status = TaskStatus.CLOSED_BY_ARBITRATION.value
    db.add(TaskEvent(task_id=task.id, actor_id=None, event="ARBITRATION_RESOLVED", detail=f"{verdict}: {resolution}"))
    db.flush()
    return arb
