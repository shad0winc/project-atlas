"""HTTP route packages for the Atlas API."""

from .health import router as health_router

__all__ = [
    "health_router",
]
