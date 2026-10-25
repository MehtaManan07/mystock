"""
Assistant HTTP API.

The surface is split by resource -- threads, messages and runs each own a
router -- and combined here under the ``/assistant`` prefix. ``main`` includes
this one combined router; the sub-routers never leave the module.
"""

from fastapi import APIRouter

from app.modules.assistant.routers.messages import router as messages_router
from app.modules.assistant.routers.runs import router as runs_router
from app.modules.assistant.routers.threads import router as threads_router

router = APIRouter(prefix="/assistant", tags=["assistant"])
router.include_router(threads_router)
router.include_router(messages_router)
router.include_router(runs_router)

__all__ = ["router"]
