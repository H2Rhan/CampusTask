from fastapi import APIRouter

from ...ai import parse_task_text
from ...schemas import AIParseIn, AIParseOut

router = APIRouter(prefix="/ai", tags=["AI 任务解析"])


@router.post("/parse", response_model=AIParseOut, summary="自然语言 → 结构化任务")
def parse(payload: AIParseIn):
    result = parse_task_text(payload.text)
    return AIParseOut(**result.__dict__)
