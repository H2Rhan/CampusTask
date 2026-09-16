"""Pydantic schemas (API v1 输入/输出契约)。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- auth
class RegisterIn(BaseModel):
    student_no: str = Field(min_length=4, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    name: str = Field(min_length=1, max_length=64)
    college: str = ""
    grade: str = ""
    phone: str = ""
    dorm_area: str = ""


class LoginIn(BaseModel):
    student_no: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# ---------------------------------------------------------------- user
class UserOut(BaseModel):
    id: int
    student_no: str
    name: str
    school: str
    college: str
    grade: str
    dorm_area: str
    is_verified: bool
    credit_score: float
    tasks_completed: int
    tasks_cancelled: int
    complaints: int
    good_rate: float
    avg_finish_minutes: float

    model_config = {"from_attributes": True}


class UserRouteIn(BaseModel):
    name: str = "日常路线"
    waypoints: list[str] = Field(min_length=2)


class UserRouteOut(BaseModel):
    id: int
    name: str
    waypoints: list[str]
    waypoint_names: list[str]
    active: bool


# ---------------------------------------------------------------- task
class TaskCreateIn(BaseModel):
    title: str = Field(default="", max_length=128)
    description: str = ""
    task_type: str = "其他"
    start: str = Field(description="起点：节点 id / 名称 / 别名")
    destination: str = Field(description="终点：节点 id / 名称 / 别名")
    reward: float = Field(gt=0, le=200)
    deadline: Optional[datetime] = None
    special_requirements: str = ""
    raw_text: str = ""  # 若来自 AI 解析，保留原文


class TaskOut(BaseModel):
    id: int
    publisher_id: int
    accepter_id: Optional[int]
    title: str
    description: str
    task_type: str
    start_node: str
    end_node: str
    start_name: str
    end_name: str
    reward: float
    deadline: Optional[datetime]
    distance: float
    est_minutes: float
    status: str
    match_percent: Optional[int] = None   # 仅“为我推荐”接口填充
    match_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskActionIn(BaseModel):
    action: str = Field(description="start / arrive_pickup / pickup / deliver / finish")


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class TaskEventOut(BaseModel):
    event: str
    detail: str
    actor_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- ai
class AIParseIn(BaseModel):
    text: str = Field(min_length=2, max_length=500)


class AIParseOut(BaseModel):
    task_type: str
    title: str
    start_node: Optional[str]
    start_name: Optional[str]
    end_node: Optional[str]
    end_name: Optional[str]
    deadline: Optional[datetime]
    reward: Optional[float]
    confidence: float
    source: str
    missing_fields: list[str]


# ---------------------------------------------------------------- map
class MapNodeOut(BaseModel):
    id: str
    name: str
    x: float
    y: float
    type: str
    aliases: list[str]


class MapEdgeOut(BaseModel):
    from_node: str
    to_node: str
    distance: float


class RouteOut(BaseModel):
    distance: float
    minutes: float
    path: list[str]
    path_names: list[str]


# ---------------------------------------------------------------- match
class MatchCandidateOut(BaseModel):
    user_id: int
    user_name: str
    credit_score: float
    marginal_distance: float
    marginal_minutes: float
    planned_route_names: list[str]
    match_percent: int
    reason: str


# ---------------------------------------------------------------- wallet
class WalletOut(BaseModel):
    balance: float
    frozen: float


class RechargeIn(BaseModel):
    amount: float = Field(gt=0, le=10000)


class TransactionOut(BaseModel):
    id: int
    kind: str
    amount: float
    balance_after: float
    frozen_after: float
    remark: str
    task_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- arbitration
class ArbitrationOpenIn(BaseModel):
    reason: str = Field(min_length=2, max_length=500)


class EvidenceIn(BaseModel):
    kind: str = Field(default="text", pattern="^(text|photo|location|other)$")
    content: str = Field(min_length=1, max_length=2000)


class ArbitrationResolveIn(BaseModel):
    verdict: str = Field(pattern="^(PUBLISHER_WIN|ACCEPTER_WIN|SPLIT)$")
    resolution: str = Field(min_length=2, max_length=1000)


class ArbitrationOut(BaseModel):
    id: int
    task_id: int
    initiator_id: int
    reason: str
    status: str
    evidence: list
    verdict: Optional[str]
    resolution: str
    suggestion: str
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------- chat
class ChatMessageOut(BaseModel):
    id: int
    task_id: int
    sender_id: Optional[int]
    msg_type: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


TokenOut.model_rebuild()
