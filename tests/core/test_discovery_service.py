"""Contract tests for the Atlas Discovery service."""

from collections.abc import Sequence

import pytest

from atlas.discovery import (
    DiscoveryCapability,
    DiscoveryHealth,
    DiscoveryIndexer,
    DiscoveryProvider,
    DiscoveryReport,
    DiscoveryService,
)
from atlas.discovery.models import DiscoveryError


class StubProvider(DiscoveryProvider):
    """Configurable in-memory provider for service tests."""

    def __init__(
        self,
        *,
        indexers: object = (),
        categories: Sequence[str] = (),
        applications: Sequence[str] = (),
    ) -> None:
        self._indexers = indexers
        self._categories = categories
        self._applications = applications

    def list_indexers(self):
        return self._indexers

    def list_categories(self) -> Sequence[str]:
        return self._categories

    def list_applications(self) -> Sequence[str]:
        return self._applications


def make_indexer(
    identifier: str,
    name: str,
    *,
    enabled: bool = True,
    protocol: str = "torrent",
    capabilities: object = (),
    categories: object = (),
    tags: object = (),
) -> DiscoveryIndexer:
    return DiscoveryIndexer(
        identifier=identifier,
        name=name,
        enabled=enabled,
        protocol=protocol,
        capabilities=capabilities,
        categories=categories,
        tags=tags,
    )


def test_service_requires_discovery_provider() -> None:
    with pytest.raises(
        DiscoveryError,
        match="provider must implement DiscoveryProvider",
    ):
        DiscoveryService(object())  # type: ignore[arg-type]


def test_service_exposes_configured_provider() -> None:
    provider = StubProvider()

    service = DiscoveryService(provider)

    assert service.provider is provider


def test_list_indexers_returns_deterministic_order() -> None:
    service = DiscoveryService(
        StubProvider(
            indexers=[
                make_indexer("z", "Zulu"),
                make_indexer("a", "alpha"),
                make_indexer("b", "Bravo"),
            ],
        )
    )

    assert tuple(
        indexer.identifier
        for indexer in service.list_indexers()
    ) == (
        "a",
        "b",
        "z",
    )


def test_list_indexers_uses_identifier_as_tie_breaker() -> None:
    service = DiscoveryService(
        StubProvider(
            indexers=[
                make_indexer("2", "Same"),
                make_indexer("1", "same"),
            ],
        )
    )

    assert tuple(
        indexer.identifier
        for indexer in service.list_indexers()
    ) == (
        "1",
        "2",
    )


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [
        (
            True,
            ("enabled",),
        ),
        (
            False,
            ("disabled",),
        ),
        (
            None,
            ("disabled", "enabled"),
        ),
    ],
)
def test_list_indexers_filters_enabled_state(
    enabled: bool | None,
    expected: tuple[str, ...],
) -> None:
    service = DiscoveryService(
        StubProvider(
            indexers=[
                make_indexer(
                    "enabled",
                    "Enabled",
                    enabled=True,
                ),
                make_indexer(
                    "disabled",
                    "Disabled",
                    enabled=False,
                ),
            ],
        )
    )

    assert tuple(
        indexer.identifier
        for indexer in service.list_indexers(enabled=enabled)
    ) == expected


@pytest.mark.parametrize(
    "enabled",
    [
        1,
        0,
        "true",
        [],
    ],
)
def test_list_indexers_rejects_invalid_enabled_filter(
    enabled: object,
) -> None:
    service = DiscoveryService(StubProvider())

    with pytest.raises(
        DiscoveryError,
        match="enabled filter must be a boolean or null",
    ):
        service.list_indexers(
            enabled=enabled,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "indexers",
    [
        None,
        "indexer",
        42,
    ],
)
def test_list_indexers_rejects_non_collection_provider_results(
    indexers: object,
) -> None:
    service = DiscoveryService(
        StubProvider(
            indexers=indexers,
        )
    )

    with pytest.raises(
        DiscoveryError,
        match="provider indexers must be a collection",
    ):
        service.list_indexers()


@pytest.mark.parametrize(
    "indexers",
    [
        [object()],
        [make_indexer("valid", "Valid"), object()],
    ],
)
def test_list_indexers_rejects_invalid_child_models(
    indexers: object,
) -> None:
    service = DiscoveryService(
        StubProvider(
            indexers=indexers,
        )
    )

    with pytest.raises(
        DiscoveryError,
        match=(
            "provider indexers must contain "
            "DiscoveryIndexer values"
        ),
    ):
        service.list_indexers()


def test_list_indexers_rejects_duplicate_identity() -> None:
    service = DiscoveryService(
        StubProvider(
            indexers=[
                make_indexer("duplicate", "First"),
                make_indexer("duplicate", "Second"),
            ],
        )
    )

    with pytest.raises(
        DiscoveryError,
        match=(
            "provider indexers contain duplicate identifier: "
            "duplicate"
        ),
    ):
        service.list_indexers()


def test_health_is_healthy_when_all_indexers_are_enabled() -> None:
    service = DiscoveryService(
        StubProvider(
            indexers=[
                make_indexer("one", "One"),
                make_indexer("two", "Two"),
            ],
        )
    )

    health = service.health()

    assert isinstance(health, DiscoveryHealth)
    assert health.score == 100
    assert health.healthy is True
    assert health.warnings == ()
    assert health.errors == ()
    assert health.details == {
        "indexer_count": 2,
        "enabled_indexer_count": 2,
        "disabled_indexer_count": 0,
    }


@pytest.mark.parametrize(
    ("disabled_count", "message"),
    [
        (
            1,
            "1 discovery indexer disabled",
        ),
        (
            2,
            "2 discovery indexers disabled",
        ),
    ],
)
def test_health_warns_about_disabled_indexers(
    disabled_count: int,
    message: str,
) -> None:
    indexers = [
        make_indexer(
            f"disabled-{index}",
            f"Disabled {index}",
            enabled=False,
        )
        for index in range(disabled_count)
    ]

    service = DiscoveryService(
        StubProvider(
            indexers=indexers,
        )
    )

    health = service.health()

    assert health.score == 95
    assert health.healthy is True
    assert health.warnings == (
        message,
    )
    assert health.errors == ()


def test_health_reports_empty_provider_as_error() -> None:
    service = DiscoveryService(StubProvider())

    health = service.health()

    assert health.score == 75
    assert health.healthy is False
    assert health.warnings == ()
    assert health.errors == (
        "No discovery indexers were returned by the provider",
    )
    assert health.details == {
        "indexer_count": 0,
        "enabled_indexer_count": 0,
        "disabled_indexer_count": 0,
    }


def test_report_aggregates_discovery_state() -> None:
    service = DiscoveryService(
        StubProvider(
            indexers=[
                make_indexer(
                    "nyaa",
                    "Nyaa",
                    capabilities=[
                        DiscoveryCapability.ANIME,
                        DiscoveryCapability.TV,
                    ],
                    categories=[
                        "Anime",
                        "TV",
                    ],
                    tags=[
                        "public",
                    ],
                ),
                make_indexer(
                    "movies",
                    "Movies",
                    enabled=False,
                    protocol="usenet",
                    capabilities=[
                        DiscoveryCapability.MOVIES,
                        DiscoveryCapability.TV,
                    ],
                    categories=[
                        "Movies",
                        "TV",
                    ],
                    tags=[
                        "public",
                        "usenet",
                    ],
                ),
            ],
        )
    )

    report = service.report()

    assert isinstance(report, DiscoveryReport)
    assert report.indexer_count == 2
    assert report.warning_count == 1
    assert report.error_count == 0
    assert report.metadata["enabled_indexer_count"] == 1
    assert report.metadata["disabled_indexer_count"] == 1
    assert report.metadata["capabilities"] == [
        "anime",
        "movies",
        "tv",
    ]
    assert report.metadata["categories"] == [
        "Anime",
        "Movies",
        "TV",
    ]
    assert report.metadata["tags"] == [
        "public",
        "usenet",
    ]

    health = report.metadata["health"]

    assert isinstance(health, dict)
    assert health["score"] == 95
    assert health["healthy"] is True
    assert health["warnings"] == [
        "1 discovery indexer disabled",
    ]
    assert health["errors"] == []


def test_report_for_empty_provider_contains_error_health() -> None:
    service = DiscoveryService(StubProvider())

    report = service.report()

    assert report.indexer_count == 0
    assert report.warning_count == 0
    assert report.error_count == 1
    assert report.metadata["enabled_indexer_count"] == 0
    assert report.metadata["disabled_indexer_count"] == 0
    assert report.metadata["capabilities"] == []
    assert report.metadata["categories"] == []
    assert report.metadata["tags"] == []
    assert report.metadata["health"]["healthy"] is False


def test_report_metadata_is_deterministic() -> None:
    service = DiscoveryService(
        StubProvider(
            indexers=[
                make_indexer(
                    "second",
                    "Second",
                    capabilities=[
                        DiscoveryCapability.TV,
                        DiscoveryCapability.ANIME,
                    ],
                    categories=[
                        "TV",
                        "Anime",
                    ],
                    tags=[
                        "zeta",
                        "alpha",
                    ],
                ),
                make_indexer(
                    "first",
                    "First",
                    capabilities=[
                        DiscoveryCapability.MOVIES,
                        DiscoveryCapability.ANIME,
                    ],
                    categories=[
                        "Movies",
                        "Anime",
                    ],
                    tags=[
                        "alpha",
                    ],
                ),
            ],
        )
    )

    report = service.report()

    assert report.metadata["capabilities"] == [
        "anime",
        "movies",
        "tv",
    ]
    assert report.metadata["categories"] == [
        "Anime",
        "Movies",
        "TV",
    ]
    assert report.metadata["tags"] == [
        "alpha",
        "zeta",
    ]

def test_list_categories_normalizes_deduplicates_and_sorts() -> None:
    provider = StubProvider(
        categories=[
            " TV ",
            "Anime",
            "tv",
            "Anime",
            "Movies",
        ],
    )
    service = DiscoveryService(provider)

    assert service.list_categories() == (
        "Anime",
        "Movies",
        "TV",
        "tv",
    )


@pytest.mark.parametrize(
    "categories",
    [
        "TV",
        b"TV",
        None,
        42,
    ],
)
def test_list_categories_requires_collection(
    categories: object,
) -> None:
    provider = StubProvider(
        categories=categories,  # type: ignore[arg-type]
    )
    service = DiscoveryService(provider)

    with pytest.raises(
        DiscoveryError,
        match="provider categories must be a collection",
    ):
        service.list_categories()


@pytest.mark.parametrize(
    "category",
    [
        "",
        "   ",
        None,
        42,
    ],
)
def test_list_categories_requires_non_empty_strings(
    category: object,
) -> None:
    provider = StubProvider(
        categories=[
            "TV",
            category,
        ],  # type: ignore[list-item]
    )
    service = DiscoveryService(provider)

    with pytest.raises(
        DiscoveryError,
        match=(
            "provider categories must contain non-empty strings"
        ),
    ):
        service.list_categories()

def test_list_applications_normalizes_deduplicates_and_sorts() -> None:
    provider = StubProvider(
        applications=[
            " Sonarr ",
            "Radarr",
            "sonarr",
            "Radarr",
        ],
    )
    service = DiscoveryService(provider)

    assert service.list_applications() == (
        "Radarr",
        "Sonarr",
        "sonarr",
    )


@pytest.mark.parametrize(
    "applications",
    [
        "Sonarr",
        b"Sonarr",
        None,
        42,
    ],
)
def test_list_applications_requires_collection(
    applications: object,
) -> None:
    provider = StubProvider(
        applications=applications,  # type: ignore[arg-type]
    )
    service = DiscoveryService(provider)

    with pytest.raises(
        DiscoveryError,
        match="provider applications must be a collection",
    ):
        service.list_applications()


@pytest.mark.parametrize(
    "application",
    [
        "",
        "   ",
        None,
        42,
    ],
)
def test_list_applications_requires_non_empty_strings(
    application: object,
) -> None:
    provider = StubProvider(
        applications=[
            "Sonarr",
            application,
        ],  # type: ignore[list-item]
    )
    service = DiscoveryService(provider)

    with pytest.raises(
        DiscoveryError,
        match=(
            "provider applications must contain non-empty strings"
        ),
    ):
        service.list_applications()
