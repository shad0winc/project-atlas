"""Version 1 routes for the Atlas HTTP API."""

from fastapi import APIRouter

from .auth import router as auth_router
from .dashboard import router as dashboard_router
from .health import router as health_router


router = APIRouter(
    prefix="/api/v1",
)

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(dashboard_router)

__all__ = [
    "router",
]
