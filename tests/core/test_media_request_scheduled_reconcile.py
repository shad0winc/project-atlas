"""Scheduled callback tests for media-request reconciliation."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path

import pytest

from atlas.media_requests import (
    JsonMediaRequestRepository,
    MediaRequest,
    MediaRequestProvider,
    MediaRequestService,
    MediaRequestType,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatusResult,
    ProviderSubmissionResult,
)
from atlas.media_requests.reconciler import (
    ReconciliationFailure,
    ReconciliationOutcome,
)
from atlas.media_requests.scheduled_reconcile import (
    DEFAULT_REQUESTS_ROOT,
    build_default_service,
    main,
    render_result,
    run_reconciliation,
)


class FactoryProvider(MediaRequestProvider):
    @property
    def name(self) -> str:
        return "example"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types=(MediaRequestType.MOVIE,),
            supports_cancellation=True,
        )

    def submit(
        self,
        request: MediaRequest,
    ) -> ProviderSubmissionResult:
        raise AssertionError("submit must not be called")

    def get_status(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        raise AssertionError("get_status must not be called")

    def cancel(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        raise AssertionError("cancel must not be called")

    def health(self) -> ProviderHealth:
        raise AssertionError("health must not be called")


class RecordingService:
    def __init__(
        self,
        outcome: ReconciliationOutcome,
    ) -> None:
        self.outcome = outcome


def test_render_result_is_deterministic() -> None:
    outcome = ReconciliationOutcome(
        considered=4,
        refreshed=2,
        skipped=1,
        failed=1,
        failures=(
            ReconciliationFailure(
                request_id="req-broken",
                error="provider unavailable",
            ),
        ),
    )

    payload = json.loads(
        render_result(outcome)
    )

    assert payload == {
        "considered": 4,
        "failed": 1,
        "failures": [
            {
                "error": "provider unavailable",
                "request_id": "req-broken",
            }
        ],
        "refreshed": 2,
        "skipped": 1,
    }


def test_run_reconciliation_uses_service_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = ReconciliationOutcome(
        considered=1,
        refreshed=1,
        skipped=0,
        failed=0,
        failures=(),
    )
    service = RecordingService(outcome)

    calls: list[object] = []

    def fake_reconcile(
        value: object,
        *,
        readiness: object,
    ) -> ReconciliationOutcome:
        calls.append(
            (
                value,
                readiness,
            )
        )
        return outcome

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "reconcile_active_requests",
        fake_reconcile,
    )

    restored = run_reconciliation(
        service_factory=lambda: service,  # type: ignore[arg-type]
    )

    assert restored is outcome
    assert len(calls) == 1
    assert calls[0][0] is service


def test_main_renders_json_and_succeeds_with_refresh_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = ReconciliationOutcome(
        considered=3,
        refreshed=2,
        skipped=0,
        failed=1,
        failures=(
            ReconciliationFailure(
                request_id="req-broken",
                error="provider unavailable",
            ),
        ),
    )

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "run_reconciliation",
        lambda **_: outcome,
    )

    stdout = StringIO()
    stderr = StringIO()

    result = main(
        [],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 0
    assert stderr.getvalue() == ""

    payload = json.loads(stdout.getvalue())
    assert payload["considered"] == 3
    assert payload["refreshed"] == 2
    assert payload["failed"] == 1
    assert payload["failures"][0]["request_id"] == "req-broken"


def test_main_rejects_arguments() -> None:
    stdout = StringIO()
    stderr = StringIO()

    result = main(
        ["unexpected"],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 2
    assert stdout.getvalue() == ""
    assert "arguments are not supported" in stderr.getvalue()


def test_main_normalizes_infrastructure_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**_: object) -> ReconciliationOutcome:
        raise RuntimeError("request repository unavailable")

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "run_reconciliation",
        fail,
    )

    stdout = StringIO()
    stderr = StringIO()

    result = main(
        [],
        stdout=stdout,
        stderr=stderr,
    )

    assert result == 1
    assert stdout.getvalue() == ""
    assert (
        "Request reconciliation failed: "
        "request repository unavailable"
        in stderr.getvalue()
    )


def test_default_service_uses_requests_directory_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "requests"

    monkeypatch.setenv(
        "ATLAS_REQUESTS_DIR",
        str(root),
    )

    provider = FactoryProvider()

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "default_jellyseerr_media_request_provider",
        lambda: provider,
    )

    published: list[
        tuple[str, dict[str, object], str]
    ] = []

    def fake_publish(
        name: str,
        payload: dict[str, object],
        *,
        source: str,
    ) -> None:
        published.append(
            (name, payload, source)
        )

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "publish_core_event",
        fake_publish,
    )

    service = build_default_service()

    assert isinstance(
        service,
        MediaRequestService,
    )
    assert isinstance(
        service.repository,
        JsonMediaRequestRepository,
    )
    assert service.repository.root == root

    # Exercise the event-publisher adapter without requiring a request.
    service._event_publisher(  # type: ignore[attr-defined]
        "request.available",
        {"request_id": "req-1"},
    )

    assert published == [
        (
            "request.available",
            {"request_id": "req-1"},
            "atlas-requests",
        )
    ]


def test_default_service_uses_canonical_requests_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "ATLAS_REQUESTS_DIR",
        raising=False,
    )

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "default_jellyseerr_media_request_provider",
        FactoryProvider,
    )

    service = build_default_service()

    assert service.repository.root == (
        DEFAULT_REQUESTS_ROOT
    )


def test_default_service_rejects_empty_requests_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_REQUESTS_DIR",
        "   ",
    )

    with pytest.raises(
        ValueError,
        match="ATLAS_REQUESTS_DIR is required",
    ):
        build_default_service()


def test_run_reconciliation_passes_jellyfin_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcome = ReconciliationOutcome(
        considered=1,
        refreshed=1,
        skipped=0,
        failed=0,
        failures=(),
    )

    service = RecordingService(outcome)
    jellyfin = object()
    readiness = object()

    calls: list[
        tuple[
            object,
            object,
        ]
    ] = []

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "default_jellyfin_provider",
        lambda: jellyfin,
    )

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "JellyfinRequestReadiness",
        lambda value: (
            readiness
            if value is jellyfin
            else pytest.fail(
                "readiness received wrong Jellyfin provider"
            )
        ),
    )

    def fake_reconcile(
        value: object,
        *,
        readiness: object,
    ) -> ReconciliationOutcome:
        calls.append(
            (
                value,
                readiness,
            )
        )
        return outcome

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "reconcile_active_requests",
        fake_reconcile,
    )

    restored = run_reconciliation(
        service_factory=lambda: service,  # type: ignore[arg-type]
    )

    assert restored is outcome
    assert calls == [
        (
            service,
            readiness,
        )
    ]


def test_default_service_remains_jellyseerr_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "requests"

    monkeypatch.setenv(
        "ATLAS_REQUESTS_DIR",
        str(root),
    )

    provider = FactoryProvider()

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "default_jellyseerr_media_request_provider",
        lambda: provider,
    )

    jellyfin_calls: list[None] = []

    monkeypatch.setattr(
        "atlas.media_requests.scheduled_reconcile."
        "default_jellyfin_provider",
        lambda: (
            jellyfin_calls.append(None)
            or object()
        ),
    )

    service = build_default_service()

    assert isinstance(
        service,
        MediaRequestService,
    )
    assert service.provider_names == (
        "example",
    )
    assert jellyfin_calls == []
