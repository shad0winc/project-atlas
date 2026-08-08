"""Application entry point for the Atlas HTTP API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from atlas_api.core.settings import AtlasAPISettings
from atlas_api.routes import v1_router


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate security-critical runtime configuration before serving."""

    AtlasAPISettings.from_environment()
    yield


def create_app() -> FastAPI:
    """Create and configure an Atlas API application instance."""

    application = FastAPI(
        title="Atlas API",
        description="Public HTTP API for Project Atlas.",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )

    application.include_router(v1_router)

    return application


app = create_app()
