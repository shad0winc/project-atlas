"""Version 1 routes for the Atlas HTTP API."""

from fastapi import APIRouter

from .auth import router as auth_router
from .dashboard import router as dashboard_router
from .dashboard_media import router as dashboard_media_router
from .media_libraries import router as media_libraries_router
from .health import router as health_router


router = APIRouter(
    prefix="/api/v1",
)

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(dashboard_media_router)
router.include_router(media_libraries_router)

__all__ = [
    "router",
]
