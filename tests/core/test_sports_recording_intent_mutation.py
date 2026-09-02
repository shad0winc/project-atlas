from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SUBSCRIPTIONS = ROOT / "modules/sports/src/subscriptions.py"
PRIVATE_API = ROOT / "modules/sports/src/private_api.py"


def test_recording_mutation_is_event_only_and_owner_scoped() -> None:
    source = SUBSCRIPTIONS.read_text(encoding="utf-8")

    assert "def update_subscription_recording(" in source
    assert '== user_id' in source
    assert '"event"' in source
    assert '"record"] = bool(record)' in source


def test_private_writer_has_recording_patch_boundary() -> None:
    source = PRIVATE_API.read_text(encoding="utf-8")

    assert "def do_PATCH(self) -> None:" in source
    assert 'suffix = "/recording"' in source
    assert "update_subscription_recording(" in source
    assert "HTTPStatus.UNPROCESSABLE_ENTITY" in source


def test_private_writer_preserves_recording_error_categories() -> None:
    source = PRIVATE_API.read_text(encoding="utf-8")

    assert '"code": "sports_subscription_not_found"' in source
    assert '"code": "sports_recording_target_unsupported"' in source
