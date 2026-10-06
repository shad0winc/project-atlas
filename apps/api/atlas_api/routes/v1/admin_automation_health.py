"""Permission-protected read-only automation observations."""
from typing import Annotated
from fastapi import APIRouter, Depends
from atlas_api.adapters import success_envelope
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas import ApiSuccessEnvelopeSchema
from atlas_api.security import require_permission
from atlas_api.services.automation_health import read_automation_health

router = APIRouter(prefix="/admin/automation-health", tags=["administration"])
require_automation_health_read = require_permission("system.health.read")


@router.get("", response_model=ApiSuccessEnvelopeSchema)
def automation_health(
    _user: Annotated[AuthenticatedUser, Depends(require_automation_health_read)],
) -> ApiSuccessEnvelopeSchema:
    return success_envelope(read_automation_health())
