"""运营统计与新增接口测试。"""
from tests.conftest import auth_headers, register


def _run_one_full_task(client, pub_no: str, acc_no: str, reward: float):
    pub = register(client, pub_no, "发布者")
    acc = register(client, acc_no, "接单者")
    client.post("/api/v1/wallet/recharge", json={"amount": 50}, headers=auth_headers(pub))
    task = client.post("/api/v1/tasks", json={
        "start": "学二食堂", "destination": "宿舍16斋", "reward": reward,
    }, headers=auth_headers(pub)).json()
    client.post(f"/api/v1/tasks/{task['id']}/accept", headers=auth_headers(acc))
    for action in ["start", "arrive_pickup", "pickup", "deliver", "finish"]:
        client.post(f"/api/v1/tasks/{task['id']}/advance", json={"action": action}, headers=auth_headers(acc))
    client.post(f"/api/v1/tasks/{task['id']}/confirm", headers=auth_headers(pub))
    return pub, acc


def test_stats_overview(client):
    _run_one_full_task(client, "20271001", "20271002", 5.0)
    _run_one_full_task(client, "20271003", "20271004", 8.0)
    # 同一发布者再发一单 → 复购
    pub1_token = client.post("/api/v1/auth/login", json={"student_no": "20271001", "password": "test-pass-1"}).json()["access_token"]
    client.post("/api/v1/tasks", json={"start": "图书馆", "destination": "宿舍16斋", "reward": 3},
                headers=auth_headers(pub1_token))

    stats = client.get("/api/v1/stats/overview").json()
    assert stats["users_total"] == 4
    assert stats["tasks_total"] == 3
    assert stats["tasks_completed"] == 2
    assert stats["completion_rate"] == round(2 / 3, 4)
    assert stats["avg_reward"] == round((5 + 8 + 3) / 3, 2)
    assert stats["repurchase_rate"] == 0.5  # 2 个发布者中 1 个发了 >=2 次
    assert stats["avg_finish_minutes"] >= 0


def test_wechat_dev_login(client):
    register(client, "20272001", "微信用户")
    r = client.post("/api/v1/auth/wechat", json={"code": "dev-20272001"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    me = client.get("/api/v1/users/me", headers=auth_headers(token)).json()
    assert me["name"] == "微信用户"

    r = client.post("/api/v1/auth/wechat", json={"code": "not-a-dev-code"})
    assert r.status_code == 400


def test_batch_assign_endpoint(client):
    # 登记两条路线 + 发布两个任务，验证批量分配
    li = register(client, "20273001", "李同学")
    zhang = register(client, "20273002", "张同学")
    pub = register(client, "20273003", "发布者")
    client.post("/api/v1/users/me/routes", json={"waypoints": ["中海国际", "西门", "学一食堂"]}, headers=auth_headers(li))
    client.post("/api/v1/users/me/routes", json={"waypoints": ["宿舍16斋", "学二食堂", "图书馆"]}, headers=auth_headers(zhang))
    client.post("/api/v1/wallet/recharge", json={"amount": 50}, headers=auth_headers(pub))
    client.post("/api/v1/tasks", json={"start": "西门菜鸟驿站", "destination": "中海国际", "reward": 5}, headers=auth_headers(pub))
    client.post("/api/v1/tasks", json={"start": "图书馆", "destination": "宿舍16斋", "reward": 3}, headers=auth_headers(pub))

    r = client.get("/api/v1/match/batch-assign")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["assignments"]) == 2
    by_title = {a["task_title"]: a["user_name"] for a in data["assignments"]}
    # 快递任务分给顺路的李同学，图书馆任务分给张同学
    names = set(by_title.values())
    assert "李同学" in names and "张同学" in names


def test_admin_arbitration_list(client):
    admin = register(client, "20260001", "管理员")
    normal = register(client, "20274001", "普通用户")
    r = client.get("/api/v1/arbitrations", headers=auth_headers(normal))
    assert r.status_code == 403
    r = client.get("/api/v1/arbitrations", headers=auth_headers(admin))
    assert r.status_code == 200
