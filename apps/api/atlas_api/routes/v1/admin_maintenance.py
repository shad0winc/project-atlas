"""Global-admin maintenance status and CSRF-protected control requests."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, StrictBool

from atlas.maintenance_control import MaintenanceControlError
from atlas_api.dependencies import get_maintenance_control_client, get_security_audit_writer
from atlas_api.security.dependencies import require_role
from atlas_api.routes.v1.auth import _require_browser_origin
from atlas_api.services.maintenance_access import control_state

router = APIRouter(prefix='/admin/maintenance',tags=['admin-maintenance'])
require_admin = require_role('global_admin')


class MaintenanceChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: StrictBool


@router.get('')
def maintenance_status(response: Response, user=Depends(require_admin), client=Depends(get_maintenance_control_client)):
    response.headers['Cache-Control'] = 'no-store'
    return control_state(client)


@router.post('')
def change_maintenance(request: Request, response: Response, change: MaintenanceChange, user=Depends(require_admin),
                       client=Depends(get_maintenance_control_client),audit=Depends(get_security_audit_writer)):
    response.headers['Cache-Control'] = 'no-store'
    _require_browser_origin(request)
    if client is None:
        raise HTTPException(503,'Maintenance control is not configured.')
    # A durable API admission event precedes the host authority's durable transition audit.
    try:
        audit.publish('security.maintenance.requested',{'user_id':user.user_id,'enabled':change.enabled})
    except Exception:
        raise HTTPException(503,'Maintenance control audit is unavailable.') from None
    try:
        return client.request('enable' if change.enabled else 'disable',actor=user.user_id)
    except MaintenanceControlError as error:
        if str(error) in ('recovery_held','operation_busy','transition_requires_host_repair'):
            raise HTTPException(409,'Maintenance remains held by an active operation or recovery.') from None
        raise HTTPException(503,'Maintenance control is unavailable.') from None
