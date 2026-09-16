"""校园图与路径算法测试。"""
from app.campus_map.graph import get_campus_graph
from app.campus_map.routing import (
    astar,
    best_insertion_route,
    dijkstra,
    marginal_cost,
    route_cost,
)


def test_shortest_path_direct_edge():
    g = get_campus_graph()
    r = dijkstra(g, "dorm_16", "canteen_2")
    assert r is not None
    assert r.distance == 380
    assert r.path == ["dorm_16", "canteen_2"]


def test_dijkstra_finds_shorter_indirect():
    g = get_campus_graph()
    # dorm_16 -> library: 直达无边，最短路应经由 canteen_2 / teach_b
    r = dijkstra(g, "dorm_16", "library")
    assert r is not None
    direct_via_canteen = 380 + 640 + 570  # dorm16-canteen2-datong-library
    assert r.distance <= direct_via_canteen
    assert r.path[0] == "dorm_16" and r.path[-1] == "library"


def test_astar_matches_dijkstra_distance():
    g = get_campus_graph()
    pairs = [("zhonghai", "teach_b"), ("dorm_1", "cs_building"), ("gate_south", "gate_north")]
    for a, b in pairs:
        d = dijkstra(g, a, b)
        s = astar(g, a, b)
        assert d is not None and s is not None
        assert abs(d.distance - s.distance) < 1e-6


def test_route_cost_order_matters():
    g = get_campus_graph()
    cost = route_cost(g, ["dorm_16", "canteen_2", "datong"])
    assert cost == 380 + 640


def test_marginal_cost_zero_when_fully_on_the_way():
    g = get_campus_graph()
    # 用户路线 宿舍16斋 -> 学二食堂 -> 图书馆；任务 学二食堂取件 -> 送到图书馆：
    # 取送点都在原路线上且顺序一致，边际成本应为 0
    mc = marginal_cost(g, ["dorm_16", "canteen_2", "library"], "canteen_2", "library")
    assert mc == 0


def test_marginal_cost_positive_when_reverse_direction():
    g = get_campus_graph()
    # 任务方向与原路线相反（宿舍->食堂 vs 食堂->宿舍），需要额外返程
    mc = marginal_cost(g, ["dorm_16", "canteen_2"], "canteen_2", "dorm_16")
    assert mc == 380


def test_marginal_cost_prefers_on_the_way_user():
    g = get_campus_graph()
    # 任务：西门菜鸟驿站 -> 学一食堂
    # 顺路用户：中海国际 -> 西门 -> 学一食堂（路线经过驿站附近）
    mc_near = marginal_cost(g, ["zhonghai", "gate_west", "canteen_1"], "cainiao_west", "canteen_1")
    # 绕路用户：宿舍16斋 -> 体育场
    mc_far = marginal_cost(g, ["dorm_16", "stadium"], "cainiao_west", "canteen_1")
    assert mc_near is not None and mc_far is not None
    assert mc_near < 300          # 只需拐进驿站（约 95m 进出）
    assert mc_far > mc_near * 3   # 跨校区绕路，边际成本显著更高


def test_best_insertion_respects_pickup_before_dropoff():
    g = get_campus_graph()
    result = best_insertion_route(g, ["dorm_5", "library"], "canteen_1", "teach_a")
    assert result is not None
    waypoints, _ = result
    assert waypoints.index("canteen_1") < waypoints.index("teach_a")
