"""Application entry point for the Atlas HTTP API."""

import asyncio
from contextlib import suppress
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from atlas_api.core.settings import AtlasAPISettings
from atlas_api.routes import v1_router
from atlas_api.routes.playback_gateway import router as playback_gateway_router


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate security-critical runtime configuration before serving."""

    AtlasAPISettings.from_environment()
    from atlas_api.routes.v1.playback import get_playback_service

    async def cleanup_live_streams() -> None:
        while True:
            try:
                await asyncio.to_thread(get_playback_service().reap_live_streams)
            except Exception:
                # Fixed text only: upstream exceptions may contain credentials.
                logging.getLogger(__name__).error(
                    "Live stream cleanup requires reconciliation"
                )
            await asyncio.sleep(15)

    worker = asyncio.create_task(cleanup_live_streams())
    try:
        yield
    finally:
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker


def create_app() -> FastAPI:
    """Create and configure an Atlas API application instance."""

    application = FastAPI(
        title="Atlas API",
        description="Public HTTP API for Project Atlas.",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=_lifespan,
    )

    application.include_router(v1_router)
    application.include_router(playback_gateway_router)

    return application


app = create_app()
