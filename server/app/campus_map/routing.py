"""Routing algorithms on the campus graph.

- Dijkstra shortest path (exact, non-negative weights)
- A* search (euclidean heuristic on node coordinates)
- Best-insertion "on-the-way" route planning for errand tasks
- Marginal cost (MC) computation, the core matching signal of CampusTask
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .graph import CampusGraph

INF = float("inf")


@dataclass
class RouteResult:
    distance: float          # meters
    minutes: float           # walking time
    path: List[str]          # node ids
    path_names: List[str]    # human-readable names


def dijkstra(graph: CampusGraph, start: str, goal: str) -> Optional[RouteResult]:
    """Classic Dijkstra. Returns None when unreachable."""
    if start not in graph.nodes or goal not in graph.nodes:
        return None
    dist: Dict[str, float] = {start: 0.0}
    prev: Dict[str, str] = {}
    pq: List[Tuple[float, str]] = [(0.0, start)]
    visited = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        if u == goal:
            break
        for v, w in graph.neighbors(u).items():
            nd = d + w
            if nd < dist.get(v, INF):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    if goal not in dist:
        return None
    return _build_result(graph, start, goal, dist[goal], prev)


def astar(graph: CampusGraph, start: str, goal: str) -> Optional[RouteResult]:
    """A* with euclidean-distance heuristic (admissible: straight line <= road)."""
    if start not in graph.nodes or goal not in graph.nodes:
        return None

    def h(nid: str) -> float:
        a, b = graph.nodes[nid], graph.nodes[goal]
        return math.hypot(a.x - b.x, a.y - b.y)

    g: Dict[str, float] = {start: 0.0}
    prev: Dict[str, str] = {}
    pq: List[Tuple[float, str]] = [(h(start), start)]
    closed = set()
    while pq:
        _, u = heapq.heappop(pq)
        if u in closed:
            continue
        closed.add(u)
        if u == goal:
            break
        for v, w in graph.neighbors(u).items():
            ng = g[u] + w
            if ng < g.get(v, INF):
                g[v] = ng
                prev[v] = u
                heapq.heappush(pq, (ng + h(v), v))
    if goal not in g:
        return None
    return _build_result(graph, start, goal, g[goal], prev)


def _build_result(graph: CampusGraph, start: str, goal: str, total: float, prev: Dict[str, str]) -> RouteResult:
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return RouteResult(
        distance=total,
        minutes=graph.distance_to_time(total),
        path=path,
        path_names=[graph.node_name(n) for n in path],
    )


def route_cost(graph: CampusGraph, waypoints: Sequence[str], engine=dijkstra) -> Optional[float]:
    """Total cost of visiting waypoints in order (shortest path between each pair)."""
    if len(waypoints) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(waypoints, waypoints[1:]):
        if a == b:
            continue
        r = engine(graph, a, b)
        if r is None:
            return None
        total += r.distance
    return total


def best_insertion_route(
    graph: CampusGraph,
    plan: Sequence[str],
    pickup: str,
    dropoff: str,
    engine=dijkstra,
) -> Optional[Tuple[List[str], float]]:
    """Insert (pickup -> dropoff) into the user's daily plan at the position
    that adds the least extra distance, keeping pickup before dropoff.

    Returns (new_waypoints, total_distance) or None when unreachable.
    """
    plan = list(plan)
    best: Optional[Tuple[List[str], float]] = None
    for i in range(len(plan) + 1):
        for j in range(i, len(plan) + 1):
            candidate = plan[:i] + [pickup] + plan[i:j] + [dropoff] + plan[j:]
            cost = route_cost(graph, candidate, engine)
            if cost is None:
                continue
            if best is None or cost < best[1]:
                best = (candidate, cost)
    return best


def marginal_cost(
    graph: CampusGraph,
    plan: Sequence[str],
    pickup: str,
    dropoff: str,
    engine=dijkstra,
) -> Optional[float]:
    """MC = cost(plan with task) - cost(original plan).

    The signature innovation metric of CampusTask: we do not look for the
    nearest user, but for the user whose *extra* travel is smallest.
    """
    original = route_cost(graph, plan, engine)
    if original is None:
        return None
    inserted = best_insertion_route(graph, plan, pickup, dropoff, engine)
    if inserted is None:
        return None
    return inserted[1] - original
