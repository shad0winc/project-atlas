"""Contract tests for Atlas Discovery domain models."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.discovery import (
    DiscoveryCapability,
    DiscoveryHealth,
    DiscoveryIndexer,
)
from atlas.discovery.models import DiscoveryError


def test_discovery_capability_values_are_stable() -> None:
    assert DiscoveryCapability.MOVIES.value == "movies"
    assert DiscoveryCapability.TV.value == "tv"
    assert DiscoveryCapability.ANIME.value == "anime"
    assert DiscoveryCapability.MUSIC.value == "music"
    assert DiscoveryCapability.BOOKS.value == "books"
    assert DiscoveryCapability.GENERAL.value == "general"
    assert DiscoveryCapability.CUSTOM.value == "custom"


def test_indexer_normalizes_identity_and_required_text() -> None:
    indexer = DiscoveryIndexer(
        identifier=12,
        name="  Nyaa  ",
        enabled=True,
        protocol="  TORRENT  ",
    )

    assert indexer.identifier == "12"
    assert indexer.name == "Nyaa"
    assert indexer.protocol == "torrent"


def test_indexer_normalizes_collections_deterministically() -> None:
    indexer = DiscoveryIndexer(
        identifier="nyaa",
        name="Nyaa",
        enabled=True,
        protocol="torrent",
        capabilities=[
            DiscoveryCapability.TV,
            "anime",
            "tv",
            DiscoveryCapability.ANIME,
        ],
        categories=[
            "TV",
            "Anime",
            "TV",
        ],
        tags=[
            "public",
            "anime",
            "public",
        ],
    )

    assert indexer.capabilities == (
        DiscoveryCapability.ANIME,
        DiscoveryCapability.TV,
    )
    assert indexer.categories == (
        "Anime",
        "TV",
    )
    assert indexer.tags == (
        "anime",
        "public",
    )


def test_indexer_normalizes_timestamps_to_utc() -> None:
    indexer = DiscoveryIndexer(
        identifier="nyaa",
        name="Nyaa",
        enabled=True,
        protocol="torrent",
        created_at="2026-07-31T12:00:00-04:00",
        updated_at="2026-07-31T17:30:00+01:00",
    )

    assert indexer.created_at == "2026-07-31T16:00:00Z"
    assert indexer.updated_at == "2026-07-31T16:30:00Z"


def test_indexer_serializes_normalized_values() -> None:
    indexer = DiscoveryIndexer(
        identifier=12,
        name="Nyaa",
        enabled=True,
        protocol="torrent",
        priority=25,
        capabilities=[
            DiscoveryCapability.TV,
            DiscoveryCapability.ANIME,
        ],
        categories=[
            "TV",
            "Anime",
        ],
        tags=[
            "public",
        ],
        created_at="2026-07-31T16:00:00Z",
    )

    assert indexer.to_dict() == {
        "identifier": "12",
        "name": "Nyaa",
        "enabled": True,
        "protocol": "torrent",
        "priority": 25,
        "capabilities": [
            "anime",
            "tv",
        ],
        "categories": [
            "Anime",
            "TV",
        ],
        "tags": [
            "public",
        ],
        "created_at": "2026-07-31T16:00:00Z",
        "updated_at": None,
    }


@pytest.mark.parametrize(
    "identifier",
    [
        "",
        "   ",
        None,
        True,
        1.5,
    ],
)
def test_indexer_rejects_invalid_identity(identifier: object) -> None:
    with pytest.raises(DiscoveryError):
        DiscoveryIndexer(
            identifier=identifier,  # type: ignore[arg-type]
            name="Nyaa",
            enabled=True,
            protocol="torrent",
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("name", ""),
        ("name", "   "),
        ("name", None),
        ("protocol", ""),
        ("protocol", "   "),
        ("protocol", None),
    ],
)
def test_indexer_rejects_invalid_required_text(
    field_name: str,
    value: object,
) -> None:
    values = {
        "identifier": "nyaa",
        "name": "Nyaa",
        "enabled": True,
        "protocol": "torrent",
    }
    values[field_name] = value

    with pytest.raises(DiscoveryError):
        DiscoveryIndexer(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "enabled",
    [
        1,
        0,
        "true",
        None,
    ],
)
def test_indexer_requires_boolean_enabled(enabled: object) -> None:
    with pytest.raises(
        DiscoveryError,
        match="enabled must be a boolean",
    ):
        DiscoveryIndexer(
            identifier="nyaa",
            name="Nyaa",
            enabled=enabled,  # type: ignore[arg-type]
            protocol="torrent",
        )


@pytest.mark.parametrize(
    "priority",
    [
        True,
        False,
        "25",
        2.5,
    ],
)
def test_indexer_rejects_invalid_priority(priority: object) -> None:
    with pytest.raises(
        DiscoveryError,
        match="priority must be an integer or null",
    ):
        DiscoveryIndexer(
            identifier="nyaa",
            name="Nyaa",
            enabled=True,
            protocol="torrent",
            priority=priority,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "capabilities",
    [
        "anime",
        42,
        ["unsupported"],
    ],
)
def test_indexer_rejects_invalid_capabilities(
    capabilities: object,
) -> None:
    with pytest.raises(DiscoveryError):
        DiscoveryIndexer(
            identifier="nyaa",
            name="Nyaa",
            enabled=True,
            protocol="torrent",
            capabilities=capabilities,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("categories", "anime"),
        ("categories", [None]),
        ("categories", [""]),
        ("tags", "public"),
        ("tags", [None]),
        ("tags", ["   "]),
    ],
)
def test_indexer_rejects_invalid_text_collections(
    field_name: str,
    value: object,
) -> None:
    values = {
        "identifier": "nyaa",
        "name": "Nyaa",
        "enabled": True,
        "protocol": "torrent",
    }
    values[field_name] = value

    with pytest.raises(DiscoveryError):
        DiscoveryIndexer(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("created_at", ""),
        ("created_at", "not-a-timestamp"),
        ("created_at", "2026-07-31T12:00:00"),
        ("updated_at", ""),
        ("updated_at", "not-a-timestamp"),
        ("updated_at", "2026-07-31T12:00:00"),
    ],
)
def test_indexer_rejects_invalid_timestamps(
    field_name: str,
    value: object,
) -> None:
    values = {
        "identifier": "nyaa",
        "name": "Nyaa",
        "enabled": True,
        "protocol": "torrent",
    }
    values[field_name] = value

    with pytest.raises(DiscoveryError):
        DiscoveryIndexer(**values)  # type: ignore[arg-type]


def test_indexer_is_immutable() -> None:
    indexer = DiscoveryIndexer(
        identifier="nyaa",
        name="Nyaa",
        enabled=True,
        protocol="torrent",
    )

    with pytest.raises(FrozenInstanceError):
        indexer.name = "Changed"  # type: ignore[misc]


def test_health_normalizes_collections_and_details() -> None:
    details = {
        "provider": "prowlarr",
    }

    health = DiscoveryHealth(
        score=95,
        warnings=[
            "Category requires review",
            "Category requires review",
        ],
        errors=[],
        details=details,
        evaluated_at="2026-07-31T12:00:00-04:00",
    )

    details["provider"] = "changed"

    assert health.score == 95
    assert health.healthy is True
    assert health.warnings == (
        "Category requires review",
    )
    assert health.errors == ()
    assert health.details == {
        "provider": "prowlarr",
    }
    assert health.evaluated_at == "2026-07-31T16:00:00Z"


def test_health_with_errors_is_not_healthy() -> None:
    health = DiscoveryHealth(
        errors=[
            "Prowlarr is unavailable",
        ],
    )

    assert health.healthy is False


def test_health_serializes_normalized_values() -> None:
    health = DiscoveryHealth(
        score=80,
        warnings=[
            "One warning",
        ],
        errors=[
            "One error",
        ],
        details={
            "provider": "prowlarr",
        },
        evaluated_at="2026-07-31T16:00:00Z",
    )

    assert health.to_dict() == {
        "score": 80,
        "healthy": False,
        "warnings": [
            "One warning",
        ],
        "errors": [
            "One error",
        ],
        "details": {
            "provider": "prowlarr",
        },
        "evaluated_at": "2026-07-31T16:00:00Z",
    }


@pytest.mark.parametrize(
    "score",
    [
        -1,
        101,
        True,
        False,
        95.5,
        "95",
        None,
    ],
)
def test_health_rejects_invalid_scores(score: object) -> None:
    with pytest.raises(
        DiscoveryError,
        match="score must be an integer between 0 and 100",
    ):
        DiscoveryHealth(
            score=score,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("warnings", "warning"),
        ("warnings", [None]),
        ("warnings", [""]),
        ("errors", "error"),
        ("errors", [None]),
        ("errors", ["   "]),
    ],
)
def test_health_rejects_invalid_message_collections(
    field_name: str,
    value: object,
) -> None:
    values = {
        field_name: value,
    }

    with pytest.raises(DiscoveryError):
        DiscoveryHealth(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "details",
    [
        [],
        (),
        "details",
        None,
    ],
)
def test_health_requires_mapping_details(details: object) -> None:
    with pytest.raises(
        DiscoveryError,
        match="details must be an object",
    ):
        DiscoveryHealth(
            details=details,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "evaluated_at",
    [
        "",
        "not-a-timestamp",
        "2026-07-31T12:00:00",
    ],
)
def test_health_rejects_invalid_timestamp(
    evaluated_at: object,
) -> None:
    with pytest.raises(DiscoveryError):
        DiscoveryHealth(
            evaluated_at=evaluated_at,  # type: ignore[arg-type]
        )


def test_health_is_immutable() -> None:
    health = DiscoveryHealth()

    with pytest.raises(FrozenInstanceError):
        health.score = 50  # type: ignore[misc]
