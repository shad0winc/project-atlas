from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from atlas.downloads import is_opaque_job_id
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_downloads_writer_client, get_security_audit_writer
from atlas_api.security.dependencies import require_permission
from atlas_api.services.downloads_writer import DownloadsWriterClient, DownloadsWriterError


router = APIRouter(prefix="/admin/downloads", tags=["admin-downloads"])
require_downloads_manage = require_permission("downloads.manage")
_ALLOWED_ACTIONS = frozenset({"stop_seeding", "resume", "remove_job"})


class DownloadActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str
    action: str


@router.post("/action")
def download_action(
    request: DownloadActionRequest,
    current_user: AuthenticatedUser = Depends(require_downloads_manage),
    writer: DownloadsWriterClient = Depends(get_downloads_writer_client),
    audit_writer=Depends(get_security_audit_writer),
) -> dict[str, object]:
    action = request.action.strip()
    job_id = request.job_id.strip()

    if action not in _ALLOWED_ACTIONS:
        raise HTTPException(status_code=400, detail="Unsupported download action.")
    if not is_opaque_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid download job identifier.")

    try:
        result = writer.mutate(job_id, action)
    except DownloadsWriterError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error

    audit_writer.publish(
        "security.downloads.admin_action",
        {
            "actor_user_id": current_user.user_id,
            "action": action,
            "job_id": job_id,
        },
    )
    return result
