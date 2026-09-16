"""边际成本智能匹配测试。"""
from app.campus_map.graph import get_campus_graph
from app.models.task import Task
from app.models.user import User
from app.services import matching_service


def _make_task(start: str, end: str, reward: float = 5.0) -> Task:
    return Task(start_node=start, end_node=end, reward=reward)


def test_on_the_way_user_ranks_first():
    g = get_campus_graph()
    task = _make_task("cainiao_west", "zhonghai")

    on_the_way = User(id=1, name="顺路同学", credit_score=100)
    on_the_way_plan = ["dorm_1", "gate_west", "zhonghai"]  # 路线经过西门，驿站就在西门旁

    far_away = User(id=2, name="绕路同学", credit_score=100)
    far_away_plan = ["dorm_16", "stadium", "gate_east"]

    results = matching_service.rank_candidates(
        task, [(on_the_way, on_the_way_plan), (far_away, far_away_plan)], graph=g
    )
    assert len(results) == 2
    assert results[0].user_name == "顺路同学"
    assert results[0].match_percent > results[1].match_percent
    assert results[0].marginal_distance < results[1].marginal_distance


def test_credit_affects_score():
    g = get_campus_graph()
    task = _make_task("library", "dorm_16")
    plan = ["dorm_16", "canteen_2", "library"]

    high = User(id=1, name="高信用", credit_score=118)
    low = User(id=2, name="低信用", credit_score=60)

    r_high = matching_service.score_candidate(g, task, high, plan)
    r_low = matching_service.score_candidate(g, task, low, plan)
    assert r_high.match_percent > r_low.match_percent


def test_zero_marginal_cost_gives_reason_text():
    g = get_campus_graph()
    task = _make_task("dorm_16", "canteen_2")
    user = User(id=1, name="正好顺路", credit_score=100)
    r = matching_service.score_candidate(g, task, user, ["dorm_16", "canteen_2"])
    assert r.marginal_distance == 0
    assert "完全顺路" in r.reason
    assert r.match_percent >= 85
