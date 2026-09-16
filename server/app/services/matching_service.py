"""智能任务匹配引擎——CampusTask 的核心算法亮点。

不是“谁离任务最近”，而是“谁完成这个任务时增加的额外成本最低”：

    MC = Cost(原路线 + 任务) - Cost(原路线)

匹配评分（方案定义）：

    Score = w1 * D_route + w2 * T_delay + w3 * C_credit + w4 * R_reward

其中 D_route / T_delay 为负向指标（边际距离/边际时间），
C_credit（信用）与 R_reward（收益）为正向指标。
最终归一化为 0–100 的“顺路匹配度”。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..campus_map.graph import CampusGraph, get_campus_graph
from ..campus_map.routing import best_insertion_route, route_cost
from ..models.task import Task
from ..models.user import User

# 评分权重（可在比赛中作为可调参数展示）
W_ROUTE = 0.45    # 边际距离（米，负向）
W_DELAY = 0.25    # 边际时间（分钟，负向）
W_CREDIT = 0.20   # 信用（0-120，正向）
W_REWARD = 0.10   # 悬赏（元，正向）

# 归一化参考量纲（津南校区尺度）
NORM_DISTANCE = 3000.0   # 3km 边际距离视为“极不顺路”
NORM_MINUTES = 45.0
NORM_CREDIT = 120.0
NORM_REWARD = 20.0


@dataclass
class MatchResult:
    user_id: int
    user_name: str
    credit_score: float
    marginal_distance: float      # 米
    marginal_minutes: float       # 分钟
    planned_route: list[str] = field(default_factory=list)      # 插入任务后的途径点
    planned_route_names: list[str] = field(default_factory=list)
    match_percent: int = 0        # 0-100 顺路匹配度
    reason: str = ""


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_candidate(
    graph: CampusGraph,
    task: Task,
    user: User,
    plan: Sequence[str],
) -> Optional[MatchResult]:
    """对单个候选用户计算边际成本与匹配度。plan 为该用户的日常路线（节点 id 序列）。"""
    if not plan:
        return None
    original = route_cost(graph, plan)
    if original is None:
        return None
    inserted = best_insertion_route(graph, plan, task.start_node, task.end_node)
    if inserted is None:
        return None

    waypoints, with_cost = inserted
    mc_distance = with_cost - original
    mc_minutes = graph.distance_to_time(mc_distance)

    score = (
        W_ROUTE * (1 - _clamp01(mc_distance / NORM_DISTANCE))
        + W_DELAY * (1 - _clamp01(mc_minutes / NORM_MINUTES))
        + W_CREDIT * _clamp01(user.credit_score / NORM_CREDIT)
        + W_REWARD * _clamp01(task.reward / NORM_REWARD)
    )
    percent = round(score * 100)

    if mc_distance < 50:
        reason = "完全顺路，几乎不增加路程"
    elif mc_distance < 300:
        reason = f"顺路，仅多走约 {mc_distance:.0f} 米"
    elif mc_distance < 800:
        reason = f"基本顺路，多走约 {mc_distance:.0f} 米"
    else:
        reason = f"绕路较多，多走约 {mc_distance:.0f} 米"

    return MatchResult(
        user_id=user.id,
        user_name=user.name,
        credit_score=user.credit_score,
        marginal_distance=round(mc_distance, 1),
        marginal_minutes=round(mc_minutes, 1),
        planned_route=waypoints,
        planned_route_names=[graph.node_name(n) for n in waypoints],
        match_percent=percent,
        reason=reason,
    )


def rank_candidates(
    task: Task,
    candidates: list[tuple[User, Sequence[str]]],
    graph: CampusGraph | None = None,
    limit: int = 10,
) -> list[MatchResult]:
    """对候选用户（连同其日常路线）排序，返回 Top-N。"""
    graph = graph or get_campus_graph()
    results: list[MatchResult] = []
    for user, plan in candidates:
        r = score_candidate(graph, task, user, plan)
        if r is not None:
            results.append(r)
    results.sort(key=lambda r: r.match_percent, reverse=True)
    return results[:limit]
