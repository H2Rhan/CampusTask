"""AI 自然语言任务解析。

双引擎策略：
1. LLM 引擎（OpenAI 兼容接口，配置 LLM_API_KEY 后启用）——强泛化能力；
2. 规则引擎（内置兜底）——地点别名映射 + 金额/时间/类型抽取，离线可用。

输出统一为 ParseResult，地点会映射到校园图节点 id。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import httpx

from ..campus_map.graph import CampusGraph, get_campus_graph
from ..core.config import settings

TASK_TYPES = ["取送物品", "带餐", "文件资料", "代购", "校内办事", "物品归还", "快递取送", "其他"]

_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("快递取送", ["快递", "取件", "菜鸟", "驿站", "包裹"]),
    ("带餐", ["带饭", "带餐", "食堂", "买饭", "带份", "外卖"]),
    ("文件资料", ["资料", "文件", "书", "打印", "讲义", "论文"]),
    ("代购", ["代购", "帮我买", "带一瓶", "超市", "便利店"]),
    ("物品归还", ["归还", "还书", "还给", "还回"]),
    ("校内办事", ["排队", "盖章", "手续", "办事", "证明", "报销"]),
    ("取送物品", ["取", "拿", "送", "捎"]),
]

_LLM_SYSTEM_PROMPT = """你是校园互助任务平台的任务解析器。用户会输入一句中文自然语言任务描述。
请抽取结构化信息，严格只输出 JSON（不要输出任何其他文字），字段如下：
{
  "task_type": "任务类型，必须从以下选择：取送物品/带餐/文件资料/代购/校内办事/物品归还/快递取送/其他",
  "title": "一句话任务标题，不超过20字",
  "start": "起点地点名称（原文中的说法），没有则为 null",
  "destination": "终点地点名称（原文中的说法），没有则为 null",
  "deadline": "截止时间，格式 HH:MM（24小时制，按用户语境推断上午/下午/晚上），没有则为 null",
  "deadline_day": "today 或 tomorrow，没有则为 null",
  "reward": 数字（悬赏金额，单位元），没有则为 null
}"""


@dataclass
class ParseResult:
    task_type: str = "其他"
    title: str = ""
    start_node: Optional[str] = None
    start_name: Optional[str] = None
    end_node: Optional[str] = None
    end_name: Optional[str] = None
    deadline: Optional[datetime] = None
    reward: Optional[float] = None
    confidence: float = 0.0
    source: str = "rules"
    missing_fields: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------- #
# public entry
# ---------------------------------------------------------------------- #
def parse_task_text(text: str, graph: CampusGraph | None = None) -> ParseResult:
    graph = graph or get_campus_graph()
    text = (text or "").strip()
    if not text:
        return ParseResult(missing_fields=["text"])
    if settings.llm_enabled:
        try:
            result = _parse_with_llm(text, graph)
            if result is not None:
                return result
        except Exception:
            pass  # 任何 LLM 故障都降级到规则引擎
    return _parse_with_rules(text, graph)


# ---------------------------------------------------------------------- #
# LLM engine
# ---------------------------------------------------------------------- #
def _parse_with_llm(text: str, graph: CampusGraph) -> Optional[ParseResult]:
    resp = httpx.post(
        f"{settings.llm_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": _LLM_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
        },
        timeout=settings.llm_timeout_seconds,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(_strip_code_fence(content))

    result = ParseResult(source="llm", confidence=0.9)
    result.task_type = data.get("task_type") if data.get("task_type") in TASK_TYPES else "其他"
    result.title = (data.get("title") or "")[:20]
    if data.get("start"):
        result.start_node = graph.resolve(data["start"])
        result.start_name = graph.node_name(result.start_node) if result.start_node else data["start"]
    if data.get("destination"):
        result.end_node = graph.resolve(data["destination"])
        result.end_name = graph.node_name(result.end_node) if result.end_node else data["destination"]
    if data.get("reward") is not None:
        result.reward = float(data["reward"])
    if data.get("deadline"):
        result.deadline = _combine_day_time(data.get("deadline_day"), data["deadline"])
    result.missing_fields = _missing(result)
    return result


def _strip_code_fence(content: str) -> str:
    content = content.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", content, re.S)
    return m.group(1).strip() if m else content


# ---------------------------------------------------------------------- #
# rule engine (offline fallback)
# ---------------------------------------------------------------------- #
def _parse_with_rules(text: str, graph: CampusGraph) -> ParseResult:
    result = ParseResult(source="rules")
    result.task_type = _extract_type(text)
    result.reward = _extract_reward(text)
    result.deadline = _extract_deadline(text)
    _extract_places(text, graph, result)
    result.title = _make_title(result, text)
    result.confidence = _estimate_confidence(result)
    result.missing_fields = _missing(result)
    return result


def _extract_type(text: str) -> str:
    for task_type, keywords in _TYPE_KEYWORDS:
        if any(k in text for k in keywords):
            return task_type
    return "其他"


def _extract_reward(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:块|元|块钱)", text)
    if m:
        return float(m.group(1))
    m = re.search(r"[¥￥]\s*(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _extract_deadline(text: str) -> Optional[datetime]:
    now = datetime.now()
    day_offset = 1 if ("明天" in text or "明日" in text) else 0

    m = re.search(r"(\d{1,2})\s*[:：点]\s*(\d{1,2})?", text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        if "下午" in text and hour < 12:
            hour += 12
        elif ("晚上" in text or "今晚" in text) and hour < 12:
            hour += 12
        elif "中午" in text and hour < 11:
            hour += 12
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return (now + timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)

    m = re.search(r"(上午|中午|下午|晚上|今晚)?\s*([一二两三四五六七八九十]{1,2})\s*点(半)?", text)
    if m:
        period, cn, half = m.group(1), m.group(2), m.group(3)
        hour = _CN_NUM.get(cn, 10 if cn == "十" else 0)
        if cn == "十":
            hour = 10
        if period in ("下午",) and hour < 12:
            hour += 12
        elif period in ("晚上", "今晚") and hour < 12:
            hour += 12
        elif period == "中午" and hour < 11:
            hour += 12
        minute = 30 if half else 0
        return (now + timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=0, microsecond=0)

    if "今晚" in text:
        return now.replace(hour=20, minute=0, second=0, microsecond=0)
    if "明早" in text or "明早" in text:
        return (now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
    return None


def _combine_day_time(day: Optional[str], hhmm: str) -> Optional[datetime]:
    m = re.match(r"(\d{1,2}):(\d{2})", hhmm)
    if not m:
        return None
    now = datetime.now()
    offset = 1 if day == "tomorrow" else 0
    return (now + timedelta(days=offset)).replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)


def _extract_places(text: str, graph: CampusGraph, result: ParseResult) -> None:
    """按文本出现位置抽取地点提及，结合方位动词判定起终点。"""
    mentions: list[tuple[int, int, str]] = []  # (pos, len, node_id)
    for nid, node in graph.nodes.items():
        for cand in (node.name, *node.aliases):
            start = 0
            while True:
                idx = text.find(cand, start)
                if idx < 0:
                    break
                mentions.append((idx, len(cand), nid))
                start = idx + len(cand)
    if not mentions:
        return
    # 去重：同一节点同一位置只保留最长匹配
    mentions.sort(key=lambda m: (m[0], -m[1]))
    dedup: list[tuple[int, int, str]] = []
    occupied_until = -1
    for pos, length, nid in mentions:
        if pos >= occupied_until:
            dedup.append((pos, length, nid))
            occupied_until = pos + length
    mentions = dedup

    start_hit: Optional[str] = None
    end_hit: Optional[str] = None
    for pos, length, nid in mentions:
        before = text[max(0, pos - 3):pos]
        after = text[pos + length:pos + length + 3]
        if any(k in before for k in ("从", "去")) or any(k in after for k in ("取", "拿")):
            if start_hit is None:
                start_hit = nid
                continue
        if any(k in before for k in ("到", "送", "送往", "送至")) or any(k in after for k in ("宿舍",)):
            if end_hit is None:
                end_hit = nid
                continue
    if start_hit is None and end_hit is None:
        if len(mentions) >= 2:
            start_hit, end_hit = mentions[0][2], mentions[-1][2]
        else:
            end_hit = mentions[0][2]
    elif start_hit is None:
        others = [m for m in mentions if m[2] != end_hit]
        start_hit = others[0][2] if others else None
    elif end_hit is None:
        others = [m for m in mentions if m[2] != start_hit]
        end_hit = others[-1][2] if others else None

    if start_hit and start_hit == end_hit:
        end_hit = None
    result.start_node = start_hit
    result.start_name = graph.node_name(start_hit) if start_hit else None
    result.end_node = end_hit
    result.end_name = graph.node_name(end_hit) if end_hit else None


def _make_title(result: ParseResult, text: str) -> str:
    if result.start_name and result.end_name:
        verb = {"快递取送": "取快递", "带餐": "带餐", "文件资料": "取送资料"}.get(result.task_type, "跑腿")
        return f"{result.start_name}{verb}到{result.end_name}"[:20]
    return text[:20]


def _estimate_confidence(result: ParseResult) -> float:
    score = 0.3
    if result.start_node:
        score += 0.25
    if result.end_node:
        score += 0.25
    if result.reward is not None:
        score += 0.1
    if result.deadline is not None:
        score += 0.1
    return round(min(score, 1.0), 2)


def _missing(result: ParseResult) -> list[str]:
    missing = []
    if not result.start_node:
        missing.append("start")
    if not result.end_node:
        missing.append("destination")
    if result.reward is None:
        missing.append("reward")
    return missing
