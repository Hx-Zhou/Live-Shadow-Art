from fastapi import APIRouter

from .assets import router as assets_router
from .script import router as script_router
from .tasks import router as tasks_router
from .textures import router as textures_router
from .websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(textures_router)
api_router.include_router(tasks_router)
api_router.include_router(assets_router)
api_router.include_router(script_router)
api_router.include_router(websocket_router)

__all__ = ["api_router"]
