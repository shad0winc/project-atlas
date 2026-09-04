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
