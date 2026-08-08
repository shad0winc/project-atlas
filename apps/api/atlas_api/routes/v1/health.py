"""Health routes for version 1 of the Atlas HTTP API."""

from fastapi import APIRouter, status

from atlas_api.schemas.health import HealthResponse


router = APIRouter(
    tags=["health"],
)


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Read Atlas API health",
)
def read_health() -> HealthResponse:
    """Return the public health state of the Atlas API process."""

    return HealthResponse(
        status="ok",
        service="atlas-api",
        api_version="v1",
    )
