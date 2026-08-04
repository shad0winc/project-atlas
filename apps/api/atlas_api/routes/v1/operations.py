"""Operations routes for version 1 of the Atlas HTTP API."""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)
from fastapi.responses import JSONResponse

from atlas.operations import (
    OperationsReportNotFoundError,
    OperationsRepository,
    OperationsService,
)
from atlas_api.adapters import (
    failure_envelope,
    success_envelope,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_operations_repository,
    get_operations_service,
)
from atlas_api.schemas import (
    ApiFailureEnvelopeSchema,
    ApiSuccessEnvelopeSchema,
)
from atlas_api.security import require_permission


OPERATIONS_REPORT_PERMISSION: Final = "system.health.read"
OPERATIONS_REPORT_NOT_FOUND_CODE: Final = (
    "operations_report_not_found"
)
OPERATIONS_REPORT_NOT_FOUND_MESSAGE: Final = (
    "Latest Operations report was not found"
)


OPERATIONS_HISTORY_DEFAULT_LIMIT: Final = 25
OPERATIONS_HISTORY_MAX_LIMIT: Final = 100


router = APIRouter(
    prefix="/operations",
    tags=["operations"],
)


require_operations_report_read = require_permission(
    OPERATIONS_REPORT_PERMISSION,
)


@router.get(
    "/report",
    response_model=ApiSuccessEnvelopeSchema,
    status_code=status.HTTP_200_OK,
    summary="Collect a live Atlas Operations report",
)
def read_operations_report(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_operations_report_read),
    ],
    service: Annotated[
        OperationsService,
        Depends(get_operations_service),
    ],
) -> ApiSuccessEnvelopeSchema:
    """Collect and return one fresh, non-persisted Operations report."""

    report = service.collect()

    return success_envelope(
        {
            "report": report,
        },
        generated_at=report.generated_at,
    )


@router.get(
    "/latest",
    response_model=ApiSuccessEnvelopeSchema,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ApiFailureEnvelopeSchema,
            "description": (
                "No persisted Operations report is available."
            ),
        },
    },
    status_code=status.HTTP_200_OK,
    summary="Read the latest persisted Atlas Operations report",
)
def read_latest_operations_report(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_operations_report_read),
    ],
    repository: Annotated[
        OperationsRepository,
        Depends(get_operations_repository),
    ],
) -> ApiSuccessEnvelopeSchema | JSONResponse:
    """Return the latest validated persisted Operations report."""

    try:
        report = repository.latest()
    except OperationsReportNotFoundError:
        failure = failure_envelope(
            OPERATIONS_REPORT_NOT_FOUND_CODE,
            OPERATIONS_REPORT_NOT_FOUND_MESSAGE,
            details={
                "resource": "operations_report",
                "selector": "latest",
            },
        )

        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=failure.model_dump(
                mode="json",
            ),
        )

    return success_envelope(
        {
            "report": report,
        },
        generated_at=report.generated_at,
    )


@router.get(
    "/history",
    response_model=ApiSuccessEnvelopeSchema,
    status_code=status.HTTP_200_OK,
    summary="Read persisted Atlas Operations report history",
)
def read_operations_history(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_operations_report_read),
    ],
    repository: Annotated[
        OperationsRepository,
        Depends(get_operations_repository),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=OPERATIONS_HISTORY_MAX_LIMIT,
            description=(
                "Maximum number of newest Operations reports "
                "to return."
            ),
        ),
    ] = OPERATIONS_HISTORY_DEFAULT_LIMIT,
) -> ApiSuccessEnvelopeSchema:
    """Return validated Operations history in newest-first order."""

    reports = repository.history(
        limit=limit,
    )

    return success_envelope(
        {
            "count": len(reports),
            "reports": reports,
        },
    )


__all__ = [
    "OPERATIONS_HISTORY_DEFAULT_LIMIT",
    "OPERATIONS_HISTORY_MAX_LIMIT",
    "OPERATIONS_REPORT_NOT_FOUND_CODE",
    "OPERATIONS_REPORT_NOT_FOUND_MESSAGE",
    "OPERATIONS_REPORT_PERMISSION",
    "read_latest_operations_report",
    "read_operations_history",
    "read_operations_report",
    "require_operations_report_read",
    "router",
]
