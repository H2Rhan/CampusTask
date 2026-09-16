"""CampusTask · 邻行 —— 校园智能互助任务平台 后端入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.router import api_router
from .core.config import settings
from .db.session import init_db

app = FastAPI(
    title="CampusTask · 邻行",
    description="校园智能互助任务平台：AI 任务理解 → 边际成本智能匹配 → 校园地图路径规划 → 可信交易 → 仲裁。",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP；生产环境收紧为小程序/前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health", tags=["系统"])
def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


app.include_router(api_router)
