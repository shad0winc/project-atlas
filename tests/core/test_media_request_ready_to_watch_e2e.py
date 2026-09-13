"""End-to-end Ready-to-Watch request reconciliation contract."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from atlas.media_requests.models import (
    MediaRequest,
    MediaRequestStatus,
    MediaRequestType,
)
from atlas.media_requests.provider import (
    MediaRequestProvider,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatusResult,
    ProviderSubmissionResult,
)
from atlas.media_requests.readiness import (
    JellyfinRequestReadiness,
)
from atlas.media_requests.reconciler import (
    reconcile_active_requests,
)
from atlas.media_requests.repository import (
    JsonMediaRequestRepository,
)
from atlas.media_requests.service import (
    MediaRequestService,
)


READY_TIME = datetime(
    2026,
    9,
    13,
    4,
    45,
    0,
    tzinfo=timezone.utc,
)


class ProcessingProvider(MediaRequestProvider):
    @property
    def name(self) -> str:
        return "jellyseerr"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types=(
                MediaRequestType.MOVIE,
            ),
            supports_submission=True,
            supports_status=True,
            supports_cancellation=True,
        )

    def validate_submission(
        self,
        request: MediaRequest,
    ) -> None:
        return None

    def submit(
        self,
        request: MediaRequest,
    ) -> ProviderSubmissionResult:
        return ProviderSubmissionResult(
            provider="jellyseerr",
            provider_request_id="42",
            status=MediaRequestStatus.APPROVED,
            submitted_at="2026-09-13T04:00:00Z",
            updated_at="2026-09-13T04:00:01Z",
        )

    def get_status(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        assert provider_request_id == "42"

        return ProviderStatusResult(
            provider="jellyseerr",
            provider_request_id="42",
            status=MediaRequestStatus.PROCESSING,
            updated_at="2026-09-13T04:40:00Z",
            available_at=None,
        )

    def cancel(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        raise AssertionError(
            "cancel must not be called"
        )

    def health(self) -> ProviderHealth:
        raise AssertionError(
            "health must not be called"
        )


class PlayableJellyfin:
    def __init__(self) -> None:
        self.lookups: list[
            tuple[str, str]
        ] = []
        self.playability_checks: list[str] = []

    def find_item_by_tmdb(
        self,
        tmdb_id: str,
        *,
        media_type: str,
    ) -> str | None:
        self.lookups.append(
            (
                tmdb_id,
                media_type,
            )
        )
        return "jellyfin-movie-001"

    def list_series_episodes(
        self,
        series_id: str,
    ) -> tuple[object, ...]:
        raise AssertionError(
            "movie readiness must not enumerate episodes"
        )

    def is_item_playable(
        self,
        item_id: str,
    ) -> bool:
        self.playability_checks.append(
            item_id
        )
        return item_id == "jellyfin-movie-001"


def test_reconciliation_promotes_to_ready_to_watch_once(
    tmp_path: Path,
) -> None:
    repository = JsonMediaRequestRepository(
        tmp_path / "requests"
    )
    provider = ProcessingProvider()

    published: list[
        tuple[
            str,
            dict[str, object],
        ]
    ] = []

    service = MediaRequestService(
        repository,
        (provider,),
        event_publisher=(
            lambda name, payload: published.append(
                (
                    name,
                    dict(payload),
                )
            )
        ),
        clock=lambda: READY_TIME,
    )

    service.create_request(
        MediaRequest(
            request_id="request-001",
            user_id="user-001",
            media_type=MediaRequestType.MOVIE,
            provider="jellyseerr",
            provider_media_id="157336",
            title="Interstellar",
            year=2014,
            created_at="2026-09-13T04:00:00Z",
        )
    )

    submitted = service.submit_request(
        "request-001"
    )

    assert (
        submitted.status
        is MediaRequestStatus.APPROVED
    )

    # Ignore create/submission lifecycle events.
    published.clear()

    jellyfin = PlayableJellyfin()
    readiness = JellyfinRequestReadiness(
        jellyfin
    )

    first = reconcile_active_requests(
        service,
        readiness=readiness,
    )

    assert first.considered == 1
    assert first.refreshed == 1
    assert first.skipped == 0
    assert first.failed == 0
    assert first.failures == ()

    persisted = service.get_request(
        "request-001"
    )

    assert (
        persisted.status
        is MediaRequestStatus.AVAILABLE
    )
    assert persisted.updated_at == (
        "2026-09-13T04:45:00Z"
    )
    assert persisted.available_at == (
        "2026-09-13T04:45:00Z"
    )
    assert persisted.terminal is True

    assert jellyfin.lookups == [
        (
            "157336",
            "movie",
        )
    ]
    assert jellyfin.playability_checks == [
        "jellyfin-movie-001",
    ]

    assert [
        name
        for name, _payload in published
    ] == [
        "request.processing",
        "request.available",
    ]

    available_events = [
        payload
        for name, payload in published
        if name == "request.available"
    ]

    assert len(available_events) == 1
    assert available_events[0]["status"] == (
        "available"
    )
    assert available_events[0]["available_at"] == (
        "2026-09-13T04:45:00Z"
    )

    # AVAILABLE is terminal, so a later scheduler pass must
    # neither refresh nor publish a duplicate completion event.
    second = reconcile_active_requests(
        service,
        readiness=readiness,
    )

    assert second.considered == 1
    assert second.refreshed == 0
    assert second.skipped == 1
    assert second.failed == 0
    assert second.failures == ()

    assert [
        name
        for name, _payload in published
        if name == "request.available"
    ] == [
        "request.available",
    ]
