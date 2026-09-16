"""匈牙利算法与批量分配测试。"""
from app.campus_map.graph import get_campus_graph
from app.models.task import Task
from app.models.user import User
from app.services.assignment_service import batch_assign, hungarian_min_cost


def test_hungarian_basic():
    # 经典 3x3：最优分配总成本 = 1+2+3 = 6 的另一形态
    cost = [
        [4, 1, 3],
        [2, 0, 5],
        [3, 2, 2],
    ]
    a = hungarian_min_cost(cost)
    total = sum(cost[i][j] for i, j in enumerate(a) if j >= 0)
    assert sorted(a) == [0, 1, 2]  # 每行匹配不同列
    assert total == 5              # (0→1, 1→0, 2→2) = 1+2+2


def test_hungarian_rectangular():
    cost = [
        [10, 19, 8, 15],
        [10, 18, 7, 17],
        [13, 16, 9, 14],
    ]
    a = hungarian_min_cost(cost)
    assert len(set(a)) == 3  # 列互不重复
    total = sum(cost[i][j] for i, j in enumerate(a))
    # 穷举最优解：row0→col0(10) + row1→col2(7) + row2→col3(14) = 31
    assert total == 31


def test_batch_assign_respects_on_the_way():
    g = get_campus_graph()
    tasks = [
        Task(id=1, title="快递到中海", publisher_id=99, start_node="cainiao_west", end_node="zhonghai", reward=5),
        Task(id=2, title="图书馆到16斋", publisher_id=99, start_node="library", end_node="dorm_16", reward=3),
    ]
    li = User(id=1, name="李同学", credit_score=100)   # 路线：中海→西门→学一（顺任务1）
    zhang = User(id=2, name="张同学", credit_score=100)  # 路线：16斋→二食堂→图书馆（顺任务2）
    candidates = [
        (li, ["zhonghai", "gate_west", "canteen_1"]),
        (zhang, ["dorm_16", "canteen_2", "library"]),
    ]
    result = batch_assign(tasks, candidates, graph=g)
    assert len(result.assignments) == 2
    assert result.unassigned_task_ids == []
    by_task = {a.task_id: a for a in result.assignments}
    # 每个任务应分给边际成本更低的那位
    assert by_task[1].user_name == "李同学"
    assert by_task[2].user_name == "张同学"
    assert result.total_marginal_distance > 0


def test_batch_assign_max_marginal_filter():
    g = get_campus_graph()
    tasks = [Task(id=1, title="超远任务", publisher_id=99, start_node="cainiao_west", end_node="cs_building", reward=5)]
    user = User(id=1, name="不顺路", credit_score=100)
    result = batch_assign(tasks, [(user, ["dorm_16", "stadium"])], graph=g, max_marginal=100)
    assert result.assignments == []
    assert result.unassigned_task_ids == [1]


def test_batch_assign_one_user_one_task():
    g = get_campus_graph()
    tasks = [
        Task(id=1, title="任务A", publisher_id=99, start_node="canteen_2", end_node="dorm_16", reward=5),
        Task(id=2, title="任务B", publisher_id=99, start_node="canteen_2", end_node="dorm_16", reward=5),
    ]
    user = User(id=1, name="独行侠", credit_score=100)
    result = batch_assign(tasks, [(user, ["dorm_16", "canteen_2"])], graph=g)
    assert len(result.assignments) == 1          # 一个用户至多一单
    assert len(result.unassigned_task_ids) == 1
