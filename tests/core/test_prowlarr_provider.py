"""Contract tests for the read-only Prowlarr Discovery provider."""

import pytest

from atlas.discovery import DiscoveryCapability
from atlas.discovery.providers import (
    DiscoveryProviderError,
    ProwlarrDiscoveryProvider,
)


def make_provider() -> ProwlarrDiscoveryProvider:
    return ProwlarrDiscoveryProvider(
        base_url="http://prowlarr:9696",
        api_key="secret-key",
    )


def test_list_indexers_normalizes_configured_indexers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider()

    responses = {
        "/api/v1/indexer": [
            {
                "id": 2,
                "name": "Nyaa.si",
                "enable": True,
                "protocol": "torrent",
                "priority": 25,
                "added": "2026-07-31T16:00:00Z",
                "tags": [],
                "capabilities": {
                    "categories": [
                        {
                            "name": "TV",
                            "subCategories": [
                                {
                                    "name": "TV/Anime",
                                },
                            ],
                        },
                    ],
                },
            },
            {
                "id": 1,
                "name": "1337x",
                "enable": False,
                "protocol": "torrent",
                "priority": 15,
                "added": None,
                "tags": [7],
                "capabilities": {
                    "categories": [
                        {
                            "name": "Movies",
                        },
                        {
                            "name": "Audio",
                        },
                    ],
                },
            },
        ],
        "/api/v1/tag": [
            {
                "id": 7,
                "label": "flaresolverr",
            },
        ],
    }

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: responses[path],
    )

    indexers = provider.list_indexers()

    assert tuple(indexer.name for indexer in indexers) == (
        "1337x",
        "Nyaa.si",
    )

    first = indexers[0]

    assert first.identifier == "1"
    assert first.enabled is False
    assert first.protocol == "torrent"
    assert first.priority == 15
    assert first.capabilities == (
        DiscoveryCapability.MOVIES,
        DiscoveryCapability.MUSIC,
    )
    assert first.categories == (
        "Audio",
        "Movies",
    )
    assert first.tags == (
        "flaresolverr",
    )
    assert first.created_at is None

    second = indexers[1]

    assert second.identifier == "2"
    assert second.capabilities == (
        DiscoveryCapability.ANIME,
        DiscoveryCapability.TV,
    )
    assert second.categories == (
        "TV",
        "TV/Anime",
    )
    assert second.created_at == "2026-07-31T16:00:00Z"


def test_list_categories_flattens_nested_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider()

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: [
            {
                "capabilities": {
                    "categories": [
                        {
                            "name": "TV",
                            "subCategories": [
                                {
                                    "name": "TV/Anime",
                                },
                                {
                                    "name": "TV/HD",
                                },
                            ],
                        },
                        {
                            "name": "Movies",
                        },
                    ],
                },
            },
            {
                "capabilities": {
                    "categories": [
                        {
                            "name": "TV",
                        },
                        {
                            "name": "Books",
                        },
                    ],
                },
            },
        ],
    )

    assert provider.list_categories() == (
        "Books",
        "Movies",
        "TV",
        "TV/Anime",
        "TV/HD",
    )


def test_list_applications_returns_enabled_unique_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider()

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: [
            {
                "name": "Sonarr",
                "enable": True,
            },
            {
                "name": "Radarr",
                "enable": True,
            },
            {
                "name": "sonarr",
                "enable": True,
            },
            {
                "name": "Disabled",
                "enable": False,
            },
        ],
    )

    assert provider.list_applications() == (
        "Radarr",
        "Sonarr",
        "sonarr",
    )


@pytest.mark.parametrize(
    ("method_name", "payload", "message"),
    [
        (
            "list_indexers",
            {},
            "Prowlarr indexer response must be an array",
        ),
        (
            "list_categories",
            "invalid",
            "Prowlarr indexer response must be an array",
        ),
        (
            "list_applications",
            None,
            "Prowlarr application response must be an array",
        ),
    ],
)
def test_provider_rejects_non_array_endpoint_payloads(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    payload: object,
    message: str,
) -> None:
    provider = make_provider()

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: payload,
    )

    with pytest.raises(
        DiscoveryProviderError,
        match=message,
    ):
        getattr(provider, method_name)()


@pytest.mark.parametrize(
    "payload",
    [
        [None],
        ["indexer"],
        [42],
    ],
)
def test_list_indexers_rejects_non_object_children(
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
) -> None:
    provider = make_provider()

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: payload,
    )

    with pytest.raises(
        DiscoveryProviderError,
        match="Prowlarr indexer response must contain objects",
    ):
        provider.list_indexers()


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "enable",
            1,
            "Prowlarr indexer enable must be a boolean",
        ),
        (
            "priority",
            True,
            "Prowlarr indexer priority must be an integer or null",
        ),
        (
            "capabilities",
            [],
            "Prowlarr indexer capabilities must be an object",
        ),
    ],
)
def test_list_indexers_rejects_invalid_indexer_fields(
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    value: object,
    message: str,
) -> None:
    provider = make_provider()

    item = {
        "id": 1,
        "name": "Indexer",
        "enable": True,
        "protocol": "torrent",
        "priority": 25,
        "tags": [],
        "capabilities": {
            "categories": [],
        },
    }
    item[field_name] = value

    responses = {
        "/api/v1/indexer": [item],
        "/api/v1/tag": [],
    }

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: responses[path],
    )

    with pytest.raises(
        DiscoveryProviderError,
        match=message,
    ):
        provider.list_indexers()


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("id", None),
        ("id", True),
        ("name", ""),
        ("name", None),
        ("protocol", ""),
        ("protocol", None),
    ],
)
def test_list_indexers_rejects_invalid_required_fields(
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    value: object,
) -> None:
    provider = make_provider()

    item = {
        "id": 1,
        "name": "Indexer",
        "enable": True,
        "protocol": "torrent",
        "priority": 25,
        "tags": [],
        "capabilities": {
            "categories": [],
        },
    }
    item[field_name] = value

    responses = {
        "/api/v1/indexer": [item],
        "/api/v1/tag": [],
    }

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: responses[path],
    )

    with pytest.raises(DiscoveryProviderError):
        provider.list_indexers()


def test_list_indexers_rejects_unknown_tag_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider()

    responses = {
        "/api/v1/indexer": [
            {
                "id": 1,
                "name": "Indexer",
                "enable": True,
                "protocol": "torrent",
                "priority": 25,
                "tags": [99],
                "capabilities": {
                    "categories": [],
                },
            },
        ],
        "/api/v1/tag": [],
    }

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: responses[path],
    )

    with pytest.raises(
        DiscoveryProviderError,
        match="Prowlarr indexer references unknown tag id: 99",
    ):
        provider.list_indexers()


@pytest.mark.parametrize(
    "tag_id",
    [
        True,
        "1",
        None,
    ],
)
def test_tag_lookup_requires_integer_ids(
    monkeypatch: pytest.MonkeyPatch,
    tag_id: object,
) -> None:
    provider = make_provider()

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: [
            {
                "id": tag_id,
                "label": "tag",
            },
        ],
    )

    with pytest.raises(
        DiscoveryProviderError,
        match="Prowlarr tag id must be an integer",
    ):
        provider._list_tag_lookup()


def test_tag_lookup_rejects_duplicate_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider()

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: [
            {
                "id": 1,
                "label": "first",
            },
            {
                "id": 1,
                "label": "second",
            },
        ],
    )

    with pytest.raises(
        DiscoveryProviderError,
        match="Prowlarr returned duplicate tag id: 1",
    ):
        provider._list_tag_lookup()


@pytest.mark.parametrize(
    "categories",
    [
        "TV",
        {},
        [None],
    ],
)
def test_list_categories_rejects_invalid_category_payloads(
    monkeypatch: pytest.MonkeyPatch,
    categories: object,
) -> None:
    provider = make_provider()

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: [
            {
                "capabilities": {
                    "categories": categories,
                },
            },
        ],
    )

    with pytest.raises(DiscoveryProviderError):
        provider.list_categories()


@pytest.mark.parametrize(
    "enabled",
    [
        1,
        "true",
        None,
    ],
)
def test_list_applications_requires_boolean_enable(
    monkeypatch: pytest.MonkeyPatch,
    enabled: object,
) -> None:
    provider = make_provider()

    monkeypatch.setattr(
        ProwlarrDiscoveryProvider,
        "_get_json",
        lambda self, path: [
            {
                "name": "Sonarr",
                "enable": enabled,
            },
        ],
    )

    with pytest.raises(
        DiscoveryProviderError,
        match="Prowlarr application enable must be a boolean",
    ):
        provider.list_applications()


@pytest.mark.parametrize(
    ("categories", "expected"),
    [
        (
            ["Movies", "Movies/HD"],
            (
                DiscoveryCapability.MOVIES,
            ),
        ),
        (
            ["TV", "TV/Anime"],
            (
                DiscoveryCapability.ANIME,
                DiscoveryCapability.TV,
            ),
        ),
        (
            ["Audio", "Books", "Manga"],
            (
                DiscoveryCapability.BOOKS,
                DiscoveryCapability.MUSIC,
            ),
        ),
        (
            ["Other"],
            (
                DiscoveryCapability.GENERAL,
            ),
        ),
    ],
)
def test_capability_inference(
    categories: list[str],
    expected: tuple[DiscoveryCapability, ...],
) -> None:
    from atlas.discovery.providers.prowlarr import _infer_capabilities

    assert _infer_capabilities(categories) == expected
