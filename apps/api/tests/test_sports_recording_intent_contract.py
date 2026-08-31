from pathlib import Path

from atlas_api.authorization.catalog import BUILT_IN_ROLES
from atlas_api.routes.v1 import sports
from atlas_api.schemas.sports import SportsRecordingIntentRequest


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "apps/api/atlas_api/services/sports.py"
ROUTES = ROOT / "apps/api/atlas_api/routes/v1/sports.py"


def test_recording_permission_identifier_is_stable() -> None:
    assert (
        sports.SPORTS_RECORDINGS_MANAGE_PERMISSION
        == "sports.recordings.manage"
    )


def test_recording_permission_is_granted_to_member_and_sports_admin() -> None:
    assert "sports.recordings.manage" in BUILT_IN_ROLES["member"].permissions
    assert (
        "sports.recordings.manage"
        in BUILT_IN_ROLES["sports_admin"].permissions
    )


def test_recording_request_is_strict_boolean() -> None:
    assert SportsRecordingIntentRequest(record=True).record is True


def test_api_service_uses_private_patch_boundary() -> None:
    source = SERVICE.read_text(encoding="utf-8")

    assert "def update_follow_recording(" in source
    assert '"/recording"' in source
    assert '"PATCH"' in source
    assert '"user_id": user_id' in source
    assert '"record": record' in source


def test_public_route_is_separately_permission_gated() -> None:
    source = ROUTES.read_text(encoding="utf-8")

    assert '"/follows/{subscription_id}/recording"' in source
    assert "Depends(require_sports_recordings_manage)" in source
    assert "service.update_follow_recording(" in source


def test_follow_creation_contract_still_defaults_recording_off() -> None:
    source = (
        ROOT
        / "modules/sports/src/subscriptions.py"
    ).read_text(encoding="utf-8")

    assert '"record": False' in source


def test_recording_transport_preserves_missing_and_unsupported_codes() -> None:
    service_source = SERVICE.read_text(encoding="utf-8")
    route_source = ROUTES.read_text(encoding="utf-8")

    assert 'code == "sports_subscription_not_found"' in service_source
    assert 'code == "sports_recording_target_unsupported"' in service_source
    assert "SportsSubscriptionNotFoundError" in route_source
    assert "status.HTTP_404_NOT_FOUND" in route_source
    assert "SportsRecordingTargetUnsupportedError" in route_source
    assert "status.HTTP_422_UNPROCESSABLE_ENTITY" in route_source
