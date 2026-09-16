"""AI 任务解析（规则引擎兜底路径）测试。"""
from app.ai import parse_task_text


def test_parse_full_sentence():
    r = parse_task_text("帮我下午五点去西门菜鸟驿站拿快递送到中海，给5块")
    assert r.task_type == "快递取送"
    assert r.start_node == "cainiao_west"
    assert r.end_node == "zhonghai"
    assert r.reward == 5.0
    assert r.deadline is not None and r.deadline.hour == 17
    assert r.missing_fields == []


def test_parse_library_to_dorm():
    r = parse_task_text("从图书馆帮我取一本书送到16斋，3元")
    assert r.task_type in ("文件资料", "取送物品")
    assert r.start_node == "library"
    assert r.end_node == "dorm_16"
    assert r.reward == 3.0


def test_parse_meal():
    r = parse_task_text("中午十二点半帮我在学一食堂带份饭到宿舍9斋，给2块")
    assert r.task_type == "带餐"
    assert r.start_node == "canteen_1"
    assert r.end_node == "dorm_9"
    assert r.deadline is not None and r.deadline.hour == 12 and r.deadline.minute == 30


def test_missing_fields_reported():
    r = parse_task_text("帮我跑个腿")
    assert "start" in r.missing_fields
    assert "destination" in r.missing_fields
    assert "reward" in r.missing_fields


def test_yuan_symbol_reward():
    r = parse_task_text("从西门菜鸟驿站取快递到东门，¥6")
    assert r.reward == 6.0
