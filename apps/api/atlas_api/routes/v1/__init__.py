"""Version 1 routes for the Atlas HTTP API."""

from fastapi import APIRouter

from .auth import router as auth_router
from .dashboard import router as dashboard_router
from .dashboard_media import router as dashboard_media_router
from .favorites import router as favorites_router
from .media_discovery import router as media_discovery_router
from .media_libraries import router as media_libraries_router
from .operations import router as operations_router
from .portal import router as portal_router
from .requests import router as requests_router
from .health import router as health_router


router = APIRouter(
    prefix="/api/v1",
)

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(dashboard_media_router)
router.include_router(favorites_router)
router.include_router(media_discovery_router)
router.include_router(media_libraries_router)
router.include_router(operations_router)
router.include_router(portal_router)
router.include_router(requests_router)

__all__ = [
    "router",
]
