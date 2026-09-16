"""多任务批量分配（数维杯算法线的工程实现）。

问题：n 个待接任务、m 个候选用户（各自有日常路线），
如何给每个任务分配至多一个用户、每个用户至多接一个任务，
使全校任务的**总边际出行成本最小**？

模型：二分图最小权完美匹配（指派问题），匈牙利算法 O(n²m)。
这是单任务 Best Insertion 的自然推广；进一步加入"每人可接多单 +
顺路打包"即演化为带容量约束的车辆路径问题（CVRP），是数维杯论文的
理论深化方向（见 docs/COMPETITION.md）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ..campus_map.graph import CampusGraph, get_campus_graph
from ..campus_map.routing import marginal_cost
from ..models.task import Task
from ..models.user import User

INF = 1e12


def hungarian_min_cost(cost: list[list[float]]) -> list[int]:
    """矩形匈牙利算法（行数 n <= 列数 m），返回每行匹配的列下标（-1=未匹配）。

    经典 1-indexed 势函数实现，O(n²m)。 cost[i][j] 为第 i 行分配到第 j 列的代价。
    """
    n = len(cost)
    assert n > 0
    m = len(cost[0])
    assert all(len(row) == m for row in cost)
    assert n <= m, "行数必须不大于列数（任务数 <= 候选数）"

    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    p = [0] * (m + 1)   # p[j] = 列 j 匹配的行
    way = [0] * (m + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(0, m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        # 增广
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1

    assignment = [-1] * n
    for j in range(1, m + 1):
        if p[j] > 0:
            assignment[p[j] - 1] = j - 1
    return assignment


@dataclass
class BatchAssignment:
    task_id: int
    task_title: str
    user_id: int
    user_name: str
    marginal_distance: float   # 米
    marginal_minutes: float    # 分钟


@dataclass
class BatchResult:
    assignments: list[BatchAssignment]
    total_marginal_distance: float
    total_marginal_minutes: float
    unassigned_task_ids: list[int]


def batch_assign(
    tasks: Sequence[Task],
    candidates: Sequence[tuple[User, Sequence[str]]],
    graph: CampusGraph | None = None,
    max_marginal: float = 3000.0,
) -> BatchResult:
    """全校任务总边际成本最小化分配。

    - tasks: 待分配任务（通常取所有 PENDING）
    - candidates: (用户, 日常路线) 列表；同一名用户多条路线时取其最小 MC
    - max_marginal: 边际成本上限（米），超过视为"无人顺路"，不强派
    """
    graph = graph or get_campus_graph()
    if not tasks or not candidates:
        return BatchResult([], 0.0, 0.0, [t.id for t in tasks])

    # 每个候选用户的最优（最小 MC）路线
    best_plans: list[tuple[User, Sequence[str]]] = []
    for user, plan in candidates:
        best_plans.append((user, plan))

    n, m = len(tasks), len(best_plans)
    cost = [[INF] * m for _ in range(n)]
    for i, task in enumerate(tasks):
        for j, (user, plan) in enumerate(best_plans):
            if user.id == task.publisher_id:
                continue  # 不能给自己跑腿
            mc = marginal_cost(graph, plan, task.start_node, task.end_node)
            if mc is not None and mc <= max_marginal:
                cost[i][j] = mc

    result = BatchResult([], 0.0, 0.0, [])
    if n <= m:
        col_of_row = hungarian_min_cost(cost)
        row_of_col = {c: r for r, c in enumerate(col_of_row) if c >= 0}
        for i in range(n):
            j = col_of_row[i]
            if j >= 0 and cost[i][j] < INF / 2:
                _accept(result, tasks[i], best_plans[j], cost[i][j], graph)
            else:
                result.unassigned_task_ids.append(tasks[i].id)
    else:
        # 任务多于候选：转置求解（每个用户至多接一单）
        cost_t = [[cost[i][j] for i in range(n)] for j in range(m)]
        col_of_row_t = hungarian_min_cost(cost_t)  # 每个用户 -> 任务
        matched_rows = set()
        for j, i in enumerate(col_of_row_t):
            if i >= 0 and cost_t[j][i] < INF / 2:
                _accept(result, tasks[i], best_plans[j], cost_t[j][i], graph)
                matched_rows.add(i)
        result.unassigned_task_ids = [tasks[i].id for i in range(n) if i not in matched_rows]

    return result


def _accept(result: BatchResult, task: Task, candidate: tuple[User, Sequence[str]], mc: float, graph: CampusGraph) -> None:
    user, _ = candidate
    result.assignments.append(BatchAssignment(
        task_id=task.id,
        task_title=task.title,
        user_id=user.id,
        user_name=user.name,
        marginal_distance=round(mc, 1),
        marginal_minutes=round(graph.distance_to_time(mc), 1),
    ))
    result.total_marginal_distance = round(result.total_marginal_distance + mc, 1)
    result.total_marginal_minutes = round(result.total_marginal_minutes + graph.distance_to_time(mc), 1)
