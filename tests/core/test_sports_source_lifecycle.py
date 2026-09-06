from pathlib import Path

import pytest

from modules.sports.src.source_lifecycle import (
    DEFAULT_RENEWAL_NOTICE_DAYS,
    MAX_CANDIDATES,
    PRIMARY_RENEWAL_NOTICE_DAYS,
    SourceKind,
    SourceLifecycleError,
    SourceLifecycleStore,
    SportsSource,
    TrustClass,
    group_source_providers,
    rank_source_candidates,
)


def _source(
    source_id: str,
    kind: SourceKind,
    *,
    priority: int = 100,
    enabled: bool = True,
    max_connections: int = 1,
) -> SportsSource:
    return SportsSource.from_mapping(
        {
            "source_id": source_id,
            "display_name": source_id,
            "kind": kind.value,
            "enabled": enabled,
            "priority": priority,
            "max_connections": max_connections,
        }
    )


def test_kind_controls_trust_class() -> None:
    assert (
        _source(
            "licensed",
            SourceKind.LICENSED_SUBSCRIPTION,
        ).trust_class
        is TrustClass.LICENSED
    )
    assert (
        _source(
            "official",
            SourceKind.OFFICIAL_FREE,
        ).trust_class
        is TrustClass.OFFICIAL
    )
    assert (
        _source(
            "ota",
            SourceKind.USER_OWNED_OTA,
        ).trust_class
        is TrustClass.USER_OWNED
    )
    assert (
        _source(
            "community",
            SourceKind.COMMUNITY_PUBLIC,
        ).trust_class
        is TrustClass.COMMUNITY_PUBLIC
    )


def test_trust_class_cannot_be_spoofed() -> None:
    with pytest.raises(
        SourceLifecycleError,
        match="trust_class",
    ):
        SportsSource.from_mapping(
            {
                "source_id": "community",
                "display_name": "Community",
                "kind": "community_public",
                "trust_class": "licensed",
                "max_connections": 1,
            }
        )


def test_licensed_subscription_metadata() -> None:
    source = SportsSource.from_mapping(
        {
            "source_id": "licensed",
            "display_name": "Licensed IPTV",
            "kind": "licensed_subscription",
            "max_connections": 1,
            "purchased_at": "2026-09-04T18:00:00Z",
            "expires_at": "2027-09-04T18:00:00Z",
            "renewal_url": "https://example.test/renew",
        }
    )

    assert source.max_connections == 1
    assert source.expires_at == "2027-09-04T18:00:00Z"
    assert (
        PRIMARY_RENEWAL_NOTICE_DAYS
        in source.renewal_notice_days
    )


def test_nonlicensed_source_cannot_have_expiration() -> None:
    with pytest.raises(
        SourceLifecycleError,
        match="only valid for licensed",
    ):
        SportsSource.from_mapping(
            {
                "source_id": "free",
                "display_name": "Official Free",
                "kind": "official_free",
                "max_connections": 1,
                "expires_at": "2027-09-04T18:00:00Z",
            }
        )


def test_renewal_url_rejects_embedded_credentials() -> None:
    with pytest.raises(
        SourceLifecycleError,
        match="embedded credentials",
    ):
        SportsSource.from_mapping(
            {
                "source_id": "licensed",
                "display_name": "Licensed",
                "kind": "licensed_subscription",
                "max_connections": 1,
                "renewal_url": (
                    "https://user:password@example.test/renew"
                ),
            }
        )


def test_primary_renewal_notice_is_mandatory() -> None:
    with pytest.raises(
        SourceLifecycleError,
        match="14-day",
    ):
        SportsSource.from_mapping(
            {
                "source_id": "licensed",
                "display_name": "Licensed",
                "kind": "licensed_subscription",
                "max_connections": 1,
                "renewal_notice_days": [30, 7, 1],
            }
        )


def test_default_renewal_cadence() -> None:
    source = _source(
        "licensed",
        SourceKind.LICENSED_SUBSCRIPTION,
    )

    assert (
        source.renewal_notice_days
        == DEFAULT_RENEWAL_NOTICE_DAYS
    )
    assert source.renewal_notice_days == (
        30,
        14,
        7,
        3,
        1,
    )


def test_max_connections_must_be_positive() -> None:
    with pytest.raises(
        SourceLifecycleError,
        match="max_connections",
    ):
        _source(
            "licensed",
            SourceKind.LICENSED_SUBSCRIPTION,
            max_connections=0,
        )


def test_candidate_ranking_is_bounded_to_four() -> None:
    sources = [
        _source(
            "licensed",
            SourceKind.LICENSED_SUBSCRIPTION,
        ),
        _source(
            "official-one",
            SourceKind.OFFICIAL_FREE,
            priority=10,
        ),
        _source(
            "official-two",
            SourceKind.OFFICIAL_FREE,
            priority=20,
        ),
        _source(
            "ota",
            SourceKind.USER_OWNED_OTA,
        ),
        _source(
            "community",
            SourceKind.COMMUNITY_PUBLIC,
        ),
    ]

    candidates = rank_source_candidates(sources)

    assert len(candidates) == MAX_CANDIDATES
    assert [
        item.source_id
        for item in candidates
    ] == [
        "licensed",
        "official-one",
        "official-two",
        "ota",
    ]


def test_community_fills_fourth_slot_when_available() -> None:
    candidates = rank_source_candidates(
        [
            _source(
                "licensed",
                SourceKind.LICENSED_SUBSCRIPTION,
            ),
            _source(
                "official",
                SourceKind.OFFICIAL_FREE,
            ),
            _source(
                "ota",
                SourceKind.USER_OWNED_OTA,
            ),
            _source(
                "iptv-org",
                SourceKind.COMMUNITY_PUBLIC,
            ),
        ]
    )

    assert candidates[3].slot == 4
    assert candidates[3].source_id == "iptv-org"
    assert (
        candidates[3].kind
        is SourceKind.COMMUNITY_PUBLIC
    )


def test_disabled_sources_are_not_candidates() -> None:
    candidates = rank_source_candidates(
        [
            _source(
                "disabled",
                SourceKind.LICENSED_SUBSCRIPTION,
                enabled=False,
            ),
            _source(
                "official",
                SourceKind.OFFICIAL_FREE,
            ),
        ]
    )

    assert [
        item.source_id
        for item in candidates
    ] == ["official"]


def test_store_round_trip_is_private_and_atomic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source-lifecycle.json"
    store = SourceLifecycleStore(path)

    expected = (
        SportsSource.from_mapping(
            {
                "source_id": "licensed",
                "display_name": "Licensed IPTV",
                "kind": "licensed_subscription",
                "max_connections": 1,
                "expires_at": (
                    "2027-09-04T18:00:00Z"
                ),
                "renewal_url": (
                    "https://example.test/renew"
                ),
            }
        ),
        _source(
            "iptv-org",
            SourceKind.COMMUNITY_PUBLIC,
            priority=900,
        ),
    )

    store.write(expected)

    # The store persists sources in canonical source_id order so
    # equivalent registries have deterministic on-disk representation.
    canonical = tuple(
        sorted(
            expected,
            key=lambda source: source.source_id,
        )
    )

    assert store.load() == canonical
    assert path.stat().st_mode & 0o777 == 0o600

    raw = path.read_text(encoding="utf-8")

    assert '"version": 1' in raw
    assert "password" not in raw.lower()
    assert "token" not in raw.lower()
    assert "api_key" not in raw.lower()


def test_store_rejects_duplicate_source_ids(
    tmp_path: Path,
) -> None:
    store = SourceLifecycleStore(
        tmp_path / "source-lifecycle.json"
    )

    duplicate = _source(
        "same",
        SourceKind.OFFICIAL_FREE,
    )

    with pytest.raises(
        SourceLifecycleError,
        match="unique",
    ):
        store.write(
            (
                duplicate,
                duplicate,
            )
        )


def test_unknown_source_fields_are_rejected() -> None:
    with pytest.raises(
        SourceLifecycleError,
        match="unsupported source fields",
    ):
        SportsSource.from_mapping(
            {
                "source_id": "unsafe",
                "display_name": "Unsafe",
                "kind": "licensed_subscription",
                "max_connections": 1,
                "password": "must-not-be-accepted",
            }
        )


def test_store_ensure_creates_private_registry(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source-lifecycle.json"

    store = SourceLifecycleStore(path)

    assert store.ensure() == ()
    assert store.load() == ()

    assert (
        path.stat().st_mode & 0o777
    ) == 0o600


def test_store_rejects_symbolic_link(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.json"

    target.write_text(
        '{"version":1,"sources":[]}\n',
        encoding="utf-8",
    )

    link = tmp_path / "source-lifecycle.json"
    link.symlink_to(target)

    with pytest.raises(
        SourceLifecycleError,
        match="symbolic link",
    ):
        SourceLifecycleStore(link).load()


def test_legacy_source_gets_provider_account_defaults() -> None:
    source = SportsSource.from_mapping(
        {
            "source_id": "legacy-source",
            "display_name": "Legacy Source",
            "kind": "licensed_subscription",
            "max_connections": 1,
        }
    )

    assert source.source_id == "legacy-source"
    assert source.provider_id == "legacy-source"
    assert source.provider_display_name == "Legacy Source"
    assert source.account_display_name == "Legacy Source"

    mapping = source.to_mapping()

    assert mapping["provider_id"] == "legacy-source"
    assert (
        mapping["provider_display_name"]
        == "Legacy Source"
    )
    assert (
        mapping["account_display_name"]
        == "Legacy Source"
    )


def test_multiple_accounts_can_share_provider_identity() -> None:
    primary = SportsSource.from_mapping(
        {
            "source_id": "provider-a-primary",
            "display_name": "Provider A / Primary",
            "provider_id": "provider-a",
            "provider_display_name": "Provider A",
            "account_display_name": "Primary",
            "kind": "licensed_subscription",
            "max_connections": 1,
            "backend_reference": "dispatcharr:m3u:2",
        }
    )

    multi = SportsSource.from_mapping(
        {
            "source_id": "provider-a-multi",
            "display_name": "Provider A / Multi",
            "provider_id": "provider-a",
            "provider_display_name": "Provider A",
            "account_display_name": "Multi-stream",
            "kind": "licensed_subscription",
            "max_connections": 5,
            "backend_reference": "dispatcharr:m3u:7",
        }
    )

    assert primary.source_id != multi.source_id
    assert primary.provider_id == multi.provider_id

    assert primary.account_display_name == "Primary"
    assert multi.account_display_name == "Multi-stream"

    assert primary.max_connections == 1
    assert multi.max_connections == 5

    assert (
        primary.backend_reference
        != multi.backend_reference
    )


def test_provider_and_account_names_are_not_stable_ids() -> None:
    before = SportsSource.from_mapping(
        {
            "source_id": "stable-account-id",
            "display_name": "Original",
            "provider_id": "stable-provider-id",
            "provider_display_name": "Original Provider",
            "account_display_name": "Original Account",
            "kind": "licensed_subscription",
            "max_connections": 1,
        }
    )

    after = SportsSource.from_mapping(
        {
            **before.to_mapping(),
            "display_name": "Renamed",
            "provider_display_name": "Renamed Provider",
            "account_display_name": "Renamed Account",
        }
    )

    assert after.source_id == before.source_id
    assert after.provider_id == before.provider_id

    assert (
        after.provider_display_name
        == "Renamed Provider"
    )
    assert (
        after.account_display_name
        == "Renamed Account"
    )


def test_provider_account_metadata_rejects_credentials() -> None:
    with pytest.raises(
        SourceLifecycleError,
        match="unsupported source fields",
    ):
        SportsSource.from_mapping(
            {
                "source_id": "safe-account",
                "display_name": "Safe",
                "provider_id": "safe-provider",
                "provider_display_name": "Safe Provider",
                "account_display_name": "Primary",
                "kind": "licensed_subscription",
                "max_connections": 1,
                "username": "must-not-be-stored-here",
            }
        )



def test_provider_aggregation_combines_account_capacity() -> None:
    sources = (
        SportsSource.from_mapping(
            {
                "source_id": "provider-a-primary",
                "display_name": "Provider A / Primary",
                "provider_id": "provider-a",
                "provider_display_name": "Provider A",
                "account_display_name": "Primary",
                "kind": "licensed_subscription",
                "enabled": True,
                "max_connections": 1,
            }
        ),
        SportsSource.from_mapping(
            {
                "source_id": "provider-a-multi",
                "display_name": "Provider A / Multi",
                "provider_id": "provider-a",
                "provider_display_name": "Provider A",
                "account_display_name": "Multi-stream",
                "kind": "licensed_subscription",
                "enabled": True,
                "max_connections": 5,
            }
        ),
    )

    providers = group_source_providers(
        sources
    )

    assert len(providers) == 1

    provider = providers[0]

    assert provider.provider_id == "provider-a"
    assert provider.display_name == "Provider A"
    assert provider.account_count == 2
    assert provider.enabled_account_count == 2

    assert (
        provider.configured_max_connections
        == 6
    )
    assert provider.enabled_max_connections == 6

    assert provider.source_ids == (
        "provider-a-multi",
        "provider-a-primary",
    )


def test_provider_aggregation_separates_disabled_capacity() -> None:
    sources = (
        SportsSource.from_mapping(
            {
                "source_id": "primary",
                "display_name": "Primary",
                "provider_id": "provider-a",
                "provider_display_name": "Provider A",
                "account_display_name": "Primary",
                "kind": "licensed_subscription",
                "enabled": True,
                "max_connections": 3,
            }
        ),
        SportsSource.from_mapping(
            {
                "source_id": "backup",
                "display_name": "Backup",
                "provider_id": "provider-a",
                "provider_display_name": "Provider A",
                "account_display_name": "Backup",
                "kind": "licensed_subscription",
                "enabled": False,
                "max_connections": 2,
            }
        ),
    )

    provider = group_source_providers(
        sources
    )[0]

    assert provider.account_count == 2
    assert provider.enabled_account_count == 1

    assert (
        provider.configured_max_connections
        == 5
    )
    assert provider.enabled_max_connections == 3


def test_provider_aggregation_rejects_name_drift() -> None:
    sources = (
        SportsSource.from_mapping(
            {
                "source_id": "one",
                "display_name": "One",
                "provider_id": "same-provider",
                "provider_display_name": "Provider One",
                "account_display_name": "One",
                "kind": "licensed_subscription",
                "max_connections": 1,
            }
        ),
        SportsSource.from_mapping(
            {
                "source_id": "two",
                "display_name": "Two",
                "provider_id": "same-provider",
                "provider_display_name": "Different Name",
                "account_display_name": "Two",
                "kind": "licensed_subscription",
                "max_connections": 1,
            }
        ),
    )

    with pytest.raises(
        SourceLifecycleError,
        match="provider_display_name",
    ):
        group_source_providers(
            sources
        )


def test_provider_aggregate_contains_no_credentials() -> None:
    source = SportsSource.from_mapping(
        {
            "source_id": "safe-source",
            "display_name": "Safe Source",
            "provider_id": "safe-provider",
            "provider_display_name": "Safe Provider",
            "account_display_name": "Primary",
            "kind": "licensed_subscription",
            "max_connections": 4,
            "backend_reference": "dispatcharr:m3u:42",
        }
    )

    payload = group_source_providers(
        (source,)
    )[0].to_mapping()

    serialized = repr(payload).lower()

    assert "password" not in serialized
    assert "username" not in serialized
    assert "server_url" not in serialized
    assert "api_key" not in serialized
    assert "token" not in serialized
    assert "backend_reference" not in payload


def test_store_rejects_provider_name_drift_before_write(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source-lifecycle.json"

    store = SourceLifecycleStore(path)

    original = (
        SportsSource.from_mapping(
            {
                "source_id": "provider-a-primary",
                "display_name": "Primary",
                "provider_id": "provider-a",
                "provider_display_name": "Provider A",
                "account_display_name": "Primary",
                "kind": "licensed_subscription",
                "max_connections": 1,
            }
        ),
    )

    store.write(original)

    before = path.read_bytes()

    invalid = (
        original[0],
        SportsSource.from_mapping(
            {
                "source_id": "provider-a-secondary",
                "display_name": "Secondary",
                "provider_id": "provider-a",
                "provider_display_name": "Different Provider Name",
                "account_display_name": "Secondary",
                "kind": "licensed_subscription",
                "max_connections": 1,
            }
        ),
    )

    with pytest.raises(
        SourceLifecycleError,
        match="provider_display_name",
    ):
        store.write(invalid)

    # The failed validation must happen before the
    # atomic persistence transaction.
    assert path.read_bytes() == before
    assert store.load() == original
