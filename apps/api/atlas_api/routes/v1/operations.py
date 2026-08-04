"""Operations routes for version 1 of the Atlas HTTP API."""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Depends, status

from atlas.operations import OperationsService
from atlas_api.adapters import success_envelope
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_operations_service
from atlas_api.schemas import ApiSuccessEnvelopeSchema
from atlas_api.security import require_permission


OPERATIONS_REPORT_PERMISSION: Final = "system.health.read"


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


__all__ = [
    "OPERATIONS_REPORT_PERMISSION",
    "get_operations_service",
    "read_operations_report",
    "require_operations_report_read",
    "router",
]
