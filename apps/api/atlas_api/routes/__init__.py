"""HTTP route packages for the Atlas API."""

from .v1 import router as v1_router

__all__ = [
    "v1_router",
]
