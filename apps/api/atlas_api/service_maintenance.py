"""Client for the narrow host Services maintenance socket."""
from functools import lru_cache
import json
import socket

OPERATIONS = frozenset({"status", "scan", "bazarr.apply", "bazarr.rollback"})
ERRORS = frozenset({
    "operation_busy", "maintenance_required", "reviewed_operation_unavailable",
    "peer_not_permitted", "control_unavailable",
})


class ServiceMaintenanceError(RuntimeError):
    """A safe, user-facing host-control failure code."""


class ServiceMaintenanceClient:
    def __init__(self, path="/run/atlas-maintenance-control/services.sock"):
        self.path = path

    def request(self, operation, actor=None):
        if operation not in OPERATIONS:
            raise ServiceMaintenanceError("control_unavailable")
        payload = {"operation": operation}
        if operation != "status":
            if not isinstance(actor, str) or not actor or len(actor) > 128:
                raise ServiceMaintenanceError("control_unavailable")
            payload["actor"] = actor
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(5)
                client.connect(self.path)
                client.sendall((json.dumps(payload) + "\n").encode())
                with client.makefile("rb") as stream:
                    raw = stream.readline(65537)
            if len(raw) > 65536 or not raw.endswith(b"\n"):
                raise ServiceMaintenanceError("control_unavailable")
            response = json.loads(raw)
            if not isinstance(response, dict) or response.get("ok") is not True:
                code = response.get("error") if isinstance(response, dict) else None
                raise ServiceMaintenanceError(code if code in ERRORS else "control_unavailable")
            value = response.get("value")
            if not isinstance(value, dict) or not set(value) <= {"job", "bazarr"}:
                raise ServiceMaintenanceError("control_unavailable")
            return value
        except (OSError, ValueError, UnicodeError) as error:
            raise ServiceMaintenanceError("control_unavailable") from error


@lru_cache(maxsize=1)
def get_service_maintenance_client():
    return ServiceMaintenanceClient()
