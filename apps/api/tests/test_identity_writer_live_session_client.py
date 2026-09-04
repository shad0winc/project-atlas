from __future__ import annotations

from typing import Any

from atlas_api.services.identity_writer import IdentityWriterClient


class RecordingIdentityWriterClient(IdentityWriterClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append((method, path, payload))
        return {"user_id": "usr-one", "override_limit": None}


def test_clear_live_session_user_override_sends_delete_with_empty_payload() -> None:
    client = RecordingIdentityWriterClient()

    result = client.clear_live_session_user_override("usr-one")

    assert result == {"user_id": "usr-one", "override_limit": None}
    assert client.calls == [
        (
            "DELETE",
            "/internal/v1/live-session-policy/users/usr-one",
            {},
        )
    ]
