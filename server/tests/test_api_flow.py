"""端到端 API 流程：注册 → 充值 → 发布（冻结）→ 接单 → 执行 → 验收（结算）→ 评价。"""
from tests.conftest import auth_headers, register


def _recharge(client, token, amount=50.0):
    r = client.post("/api/v1/wallet/recharge", json={"amount": amount}, headers=auth_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


def _create_task(client, token, reward=5.0):
    r = client.post("/api/v1/tasks", json={
        "start": "图书馆", "destination": "中海国际宿舍区",
        "reward": reward, "task_type": "文件资料",
    }, headers=auth_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_full_task_lifecycle(client):
    pub = register(client, "20261111", "韩同学")
    acc = register(client, "20262222", "张同学")
    _recharge(client, pub, 50.0)

    # 发布：冻结 5 元
    task = _create_task(client, pub, 5.0)
    assert task["status"] == "PENDING"
    assert task["start_node"] == "library"
    assert task["end_node"] == "zhonghai"
    assert task["distance"] > 0
    wallet = client.get("/api/v1/wallet/me", headers=auth_headers(pub)).json()
    assert wallet["balance"] == 45.0 and wallet["frozen"] == 5.0

    # 接单
    r = client.post(f"/api/v1/tasks/{task['id']}/accept", headers=auth_headers(acc))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ACCEPTED"

    # 自己接自己的单 → 拒绝
    task2 = _create_task(client, pub, 3.0)
    r = client.post(f"/api/v1/tasks/{task2['id']}/accept", headers=auth_headers(pub))
    assert r.status_code == 400

    # 快捷操作走完状态机
    for action in ["start", "arrive_pickup", "pickup", "deliver", "finish"]:
        r = client.post(f"/api/v1/tasks/{task['id']}/advance", json={"action": action}, headers=auth_headers(acc))
        assert r.status_code == 200, (action, r.text)
    assert r.json()["status"] == "PENDING_CONFIRM"

    # 接单者不能替发布者验收
    r = client.post(f"/api/v1/tasks/{task['id']}/confirm", headers=auth_headers(acc))
    assert r.status_code == 400

    # 发布者验收 → 自动结算
    r = client.post(f"/api/v1/tasks/{task['id']}/confirm", headers=auth_headers(pub))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SETTLED"

    pub_wallet = client.get("/api/v1/wallet/me", headers=auth_headers(pub)).json()
    acc_wallet = client.get("/api/v1/wallet/me", headers=auth_headers(acc)).json()
    assert pub_wallet["balance"] == 42.0 and pub_wallet["frozen"] == 3.0  # task2 还冻结 3 元
    assert acc_wallet["balance"] == 5.0

    # 评价 → 信用与好评率
    r = client.post(f"/api/v1/tasks/{task['id']}/review", json={"rating": 5, "comment": "很快！"},
                    headers=auth_headers(pub))
    assert r.status_code == 200
    profile = client.get("/api/v1/users/me", headers=auth_headers(acc)).json()
    assert profile["tasks_completed"] == 1
    assert profile["good_rate"] == 1.0
    assert profile["credit_score"] > 100


def test_cancel_returns_frozen_reward(client):
    pub = register(client, "20263333", "李同学")
    _recharge(client, pub, 30.0)
    task = _create_task(client, pub, 8.0)
    r = client.post(f"/api/v1/tasks/{task['id']}/cancel", headers=auth_headers(pub))
    assert r.status_code == 200, r.text
    wallet = client.get("/api/v1/wallet/me", headers=auth_headers(pub)).json()
    assert wallet["balance"] == 30.0 and wallet["frozen"] == 0.0


def test_illegal_state_jump_rejected(client):
    pub = register(client, "20264444", "王同学")
    acc = register(client, "20265555", "赵同学")
    _recharge(client, pub, 30.0)
    task = _create_task(client, pub, 5.0)
    client.post(f"/api/v1/tasks/{task['id']}/accept", headers=auth_headers(acc))
    # ACCEPTED 状态不能直接 finish
    r = client.post(f"/api/v1/tasks/{task['id']}/advance", json={"action": "finish"}, headers=auth_headers(acc))
    assert r.status_code == 400


def test_arbitration_flow(client):
    pub = register(client, "20260001", "管理员")  # 管理员学号
    acc = register(client, "20266666", "钱同学")
    pub2 = register(client, "20267777", "孙同学")
    _recharge(client, pub2, 30.0)
    task = _create_task(client, pub2, 10.0)
    client.post(f"/api/v1/tasks/{task['id']}/accept", headers=auth_headers(acc))

    # 发布者发起仲裁
    r = client.post(f"/api/v1/tasks/{task['id']}/arbitrate", json={"reason": "他没有把东西送给我"},
                    headers=auth_headers(pub2))
    assert r.status_code == 200, r.text
    arb = r.json()
    assert "PUBLISHER_WIN" in arb["suggestion"]  # 规则引擎：无取件记录

    # 接单者提交证据
    r = client.post(f"/api/v1/arbitrations/{arb['id']}/evidence",
                    json={"kind": "text", "content": "我到了宿舍楼下但联系不上他"},
                    headers=auth_headers(acc))
    assert r.status_code == 200

    # 非管理员不能裁决
    r = client.post(f"/api/v1/arbitrations/{arb['id']}/resolve",
                    json={"verdict": "PUBLISHER_WIN", "resolution": "测试"}, headers=auth_headers(pub2))
    assert r.status_code == 403

    # 管理员裁决：悬赏退回发布者
    r = client.post(f"/api/v1/arbitrations/{arb['id']}/resolve",
                    json={"verdict": "PUBLISHER_WIN", "resolution": "无取件记录，支持发布者"},
                    headers=auth_headers(pub))
    assert r.status_code == 200, r.text
    wallet = client.get("/api/v1/wallet/me", headers=auth_headers(pub2)).json()
    assert wallet["balance"] == 30.0 and wallet["frozen"] == 0.0


def test_recommend_for_me(client):
    pub = register(client, "20268888", "发布者")
    me = register(client, "20269999", "顺路者")
    _recharge(client, pub, 30.0)

    # 我的日常路线：宿舍16斋 → 学二食堂 → 图书馆
    r = client.post("/api/v1/users/me/routes",
                    json={"name": "日常", "waypoints": ["宿舍16斋", "学二食堂", "图书馆"]},
                    headers=auth_headers(me))
    assert r.status_code == 200, r.text

    # 顺路任务：学二食堂 → 宿舍16斋
    _create_task(client, pub, 5.0)  # library -> zhonghai（不顺路）
    r = client.post("/api/v1/tasks", json={
        "start": "学二食堂", "destination": "宿舍16斋", "reward": 3.0,
    }, headers=auth_headers(pub))
    assert r.status_code == 200

    recs = client.get("/api/v1/match/for-me", headers=auth_headers(me)).json()
    assert len(recs) == 2
    assert recs[0]["match_percent"] >= recs[1]["match_percent"]
    assert recs[0]["start_node"] == "canteen_2"  # 顺路任务排第一


def test_ai_parse_endpoint(client):
    r = client.post("/api/v1/ai/parse", json={"text": "下午五点去西门菜鸟驿站拿快递送到中海，给5块"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["start_node"] == "cainiao_west"
    assert data["end_node"] == "zhonghai"
    assert data["reward"] == 5.0


def test_map_endpoints(client):
    nodes = client.get("/api/v1/map/nodes").json()
    assert len(nodes) >= 20
    r = client.get("/api/v1/map/route", params={"start": "宿舍16斋", "end": "图书馆"}).json()
    assert r["distance"] > 0
    assert r["path_names"][0] == "宿舍16斋"
    r2 = client.get("/api/v1/map/route", params={"start": "宿舍16斋", "end": "图书馆", "engine": "astar"}).json()
    assert abs(r["distance"] - r2["distance"]) < 1e-6
