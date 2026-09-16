from fastapi import APIRouter

from . import ai, arbitration, auth, chat, map, match, tasks, users, wallet

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(tasks.router)
api_router.include_router(map.router)
api_router.include_router(match.router)
api_router.include_router(ai.router)
api_router.include_router(wallet.router)
api_router.include_router(arbitration.router)
api_router.include_router(chat.router)
