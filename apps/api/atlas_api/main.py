"""Application entry point for the Atlas HTTP API."""

from fastapi import FastAPI

from atlas_api.routes import health_router


def create_app() -> FastAPI:
    """Create and configure an Atlas API application instance."""

    application = FastAPI(
        title="Atlas API",
        description="Public HTTP API for Project Atlas.",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    application.include_router(health_router)

    return application


app = create_app()
