from __future__ import annotations

import pytest

from dispatcharr_admin import (
    DispatcharrAdminError,
    SafeDispatcharrStream,
)
from live_source_orchestration import (
    build_live_source_provisioning_plan,
    resolve_event_live_source_content,
)
from live_source_resolver import (
    LiveSourceMatchKind,
)
from source_lifecycle import SportsSource


def _event() -> dict[str, object]:
    return {
        "provider": "thesportsdb",
        "provider_event_id": "2475374",
        "name": (
            "Seattle Seahawks vs "
            "New England Patriots"
        ),
        "sport": "American Football",
        "league": "NFL",
        "start_at": (
            "2026-09-10T00:20:00+00:00"
        ),
        "home_team": "Seattle Seahawks",
        "away_team": (
            "New England Patriots"
        ),
    }


def _source(
    source_id: str,
    account_id: int,
    *,
    enabled: bool = True,
    priority: int = 100,
) -> SportsSource:
    return SportsSource.from_mapping(
        {
            "source_id": source_id,
            "display_name": source_id,
            "provider_id": source_id,
            "provider_display_name": (
                source_id
            ),
            "account_display_name": (
                source_id
            ),
            "kind": (
                "licensed_subscription"
            ),
            "enabled": enabled,
            "priority": priority,
            "max_connections": 1,
            "backend_reference": (
                f"dispatcharr:m3u:{account_id}"
            ),
        }
    )


def _stream(
    stream_id: int,
    name: str,
    account_id: int,
    *,
    group_name: str | None = "NFL",
    is_stale: bool = False,
) -> SafeDispatcharrStream:
    return SafeDispatcharrStream(
        stream_id=stream_id,
        name=name,
        m3u_account_id=account_id,
        group_name=group_name,
        is_stale=is_stale,
    )


class FakeDispatcharr:
    def __init__(
        self,
        streams_by_account: dict[
            int,
            tuple[SafeDispatcharrStream, ...],
        ],
    ) -> None:
        self.streams_by_account = (
            streams_by_account
        )
        self.calls: list[int] = []

    def list_streams(
        self,
        *,
        account_id: int,
    ) -> tuple[SafeDispatcharrStream, ...]:
        self.calls.append(account_id)
        return self.streams_by_account.get(
            account_id,
            (),
        )


def test_queries_each_eligible_account_once_and_resolves_content() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    175,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
            3: (
                _stream(
                    275,
                    "NFL Seattle Seahawks",
                    3,
                ),
                _stream(
                    276,
                    "NFL New England Patriots",
                    3,
                ),
            ),
        }
    )

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(
            _source(
                "primary",
                2,
                priority=200,
            ),
            _source(
                "fallback",
                3,
                priority=100,
            ),
        ),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert dispatcharr.calls == [2, 3]
    assert result is not None
    assert (
        result.match_kind
        is LiveSourceMatchKind.EXACT_EVENT
    )
    assert result.resource_source_ids == (
        "primary",
    )


def test_disabled_and_unrelated_sources_are_not_queried() -> None:
    disabled = _source(
        "disabled",
        2,
        enabled=False,
    )

    unrelated = SportsSource.from_mapping(
        {
            "source_id": "unrelated",
            "display_name": "Unrelated",
            "provider_id": "unrelated",
            "provider_display_name": (
                "Unrelated"
            ),
            "account_display_name": (
                "Unrelated"
            ),
            "kind": "official_free",
            "enabled": True,
            "priority": 100,
            "max_connections": 1,
            "backend_reference": (
                "other:backend:3"
            ),
        }
    )

    dispatcharr = FakeDispatcharr({})

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(
            disabled,
            unrelated,
        ),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert dispatcharr.calls == []
    assert result is None


def test_duplicate_account_reference_is_queried_once_but_resolver_fails_closed() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    175,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match=(
            "multiple enabled Sports "
            "sources reference the same "
            "Dispatcharr account"
        ),
    ):
        resolve_event_live_source_content(
            event=_event(),
            sources=(
                _source(
                    "one",
                    2,
                ),
                _source(
                    "two",
                    2,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )

    assert dispatcharr.calls == [2]


def test_legacy_numeric_account_reference_is_discovered() -> None:
    legacy = SportsSource.from_mapping(
        {
            "source_id": "legacy",
            "display_name": "Legacy",
            "provider_id": "legacy",
            "provider_display_name": "Legacy",
            "account_display_name": "Legacy",
            "kind": "licensed_subscription",
            "enabled": True,
            "priority": 100,
            "max_connections": 1,
            "backend_reference": "2",
        }
    )

    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    175,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(legacy,),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert dispatcharr.calls == [2]
    assert result is not None
    assert result.resource_source_ids == (
        "legacy",
    )


def test_authoritative_empty_streams_resolve_to_none() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (),
        }
    )

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(
            _source(
                "primary",
                2,
            ),
        ),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert dispatcharr.calls == [2]
    assert result is None


def test_dispatcharr_failure_is_not_converted_to_empty_state() -> None:
    class UnavailableDispatcharr:
        def list_streams(
            self,
            *,
            account_id: int,
        ) -> tuple[
            SafeDispatcharrStream,
            ...,
        ]:
            raise DispatcharrAdminError(
                "Dispatcharr unavailable"
            )

    with pytest.raises(
        DispatcharrAdminError,
        match="Dispatcharr unavailable",
    ):
        resolve_event_live_source_content(
            event=_event(),
            sources=(
                _source(
                    "primary",
                    2,
                ),
            ),
            dispatcharr=UnavailableDispatcharr(),  # type: ignore[arg-type]
        )


def test_safe_stream_metadata_is_forwarded_without_backend_secrets() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    175,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                    group_name="NFL",
                ),
            ),
        }
    )

    result = resolve_event_live_source_content(
        event=_event(),
        sources=(
            _source(
                "primary",
                2,
            ),
        ),
        dispatcharr=dispatcharr,  # type: ignore[arg-type]
    )

    assert result is not None

    payload = result.to_mapping()
    rendered = repr(payload).casefold()

    assert "password" not in rendered
    assert "username" not in rendered
    assert "server_url" not in rendered
    assert "backend_reference" not in rendered
    assert "token" not in rendered



def test_build_provisioning_plan_uses_canonical_shared_event_identity() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    900,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    event = _event()

    resolution = (
        resolve_event_live_source_content(
            event=event,
            sources=(
                _source(
                    "primary",
                    2,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )
    )

    assert resolution is not None

    plan = (
        build_live_source_provisioning_plan(
            event=event,
            resolution=resolution,
        )
    )

    assert plan.source_id == (
        "thesportsdb-2475374"
    )

    assert plan.atlas_channel_id == (
        "sports-live-thesportsdb-2475374"
    )

    assert plan.name == (
        "Seattle Seahawks vs "
        "New England Patriots"
    )

    assert plan.provider == "thesportsdb"
    assert (
        plan.provider_event_id
        == "2475374"
    )

    assert plan.resource_source_ids == (
        "primary",
    )

    assert plan.stream_ids == (
        900,
    )


def test_build_provisioning_plan_preserves_ranked_source_and_stream_order() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    201,
                    "NFL PATRIOTS HD",
                    2,
                ),
                _stream(
                    202,
                    "NFL SEAHAWKS HD",
                    2,
                ),
            ),
            3: (
                _stream(
                    301,
                    "NFL PATRIOTS HD",
                    3,
                ),
                _stream(
                    302,
                    "NFL SEAHAWKS HD",
                    3,
                ),
            ),
        }
    )

    event = _event()

    resolution = (
        resolve_event_live_source_content(
            event=event,
            sources=(
                _source(
                    "later",
                    2,
                    priority=200,
                ),
                _source(
                    "first",
                    3,
                    priority=100,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )
    )

    assert resolution is not None
    assert resolution.resource_source_ids == (
        "first",
        "later",
    )

    plan = (
        build_live_source_provisioning_plan(
            event=event,
            resolution=resolution,
        )
    )

    assert [
        item.source_id
        for item
        in plan.source_streams
    ] == [
        "first",
        "later",
    ]

    assert [
        item.stream_ids
        for item
        in plan.source_streams
    ] == [
        (302, 301),
        (202, 201),
    ]

    assert plan.stream_ids == (
        302,
        301,
        202,
        201,
    )


def test_build_provisioning_plan_rejects_mismatched_event_identity() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    900,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    event = _event()

    resolution = (
        resolve_event_live_source_content(
            event=event,
            sources=(
                _source(
                    "primary",
                    2,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )
    )

    assert resolution is not None

    wrong_event = dict(event)
    wrong_event[
        "provider_event_id"
    ] = "different-event"

    with pytest.raises(
        ValueError,
        match=(
            "resolution event identity "
            "does not match event"
        ),
    ):
        build_live_source_provisioning_plan(
            event=wrong_event,
            resolution=resolution,
        )


def test_provisioning_plan_is_secret_and_url_free() -> None:
    dispatcharr = FakeDispatcharr(
        {
            2: (
                _stream(
                    900,
                    (
                        "NFL Seattle Seahawks vs "
                        "New England Patriots"
                    ),
                    2,
                ),
            ),
        }
    )

    event = _event()

    resolution = (
        resolve_event_live_source_content(
            event=event,
            sources=(
                _source(
                    "primary",
                    2,
                ),
            ),
            dispatcharr=dispatcharr,  # type: ignore[arg-type]
        )
    )

    assert resolution is not None

    plan = (
        build_live_source_provisioning_plan(
            event=event,
            resolution=resolution,
        )
    )

    rendered = repr(
        plan.to_mapping()
    ).casefold()

    for forbidden in (
        "password",
        "username",
        "server_url",
        "backend_reference",
        "access_token",
        "api_key",
        "http://",
        "https://",
    ):
        assert forbidden not in rendered


class FakeChannelBindings:
    def __init__(self, binding=None) -> None:
        self.binding = binding
        self.resolve_calls = []
        self.set_calls = []

    def resolve(self, atlas_channel_id):
        self.resolve_calls.append(
            atlas_channel_id
        )
        return self.binding

    def set(
        self,
        atlas_channel_id,
        channel_id,
        channel_uuid,
    ):
        from dispatcharr_channel_bindings import (
            DispatcharrChannelBinding,
        )

        self.set_calls.append(
            (
                atlas_channel_id,
                channel_id,
                channel_uuid,
            )
        )

        self.binding = DispatcharrChannelBinding(
            atlas_channel_id=atlas_channel_id,
            dispatcharr_channel_id=channel_id,
            dispatcharr_channel_uuid=channel_uuid,
        )

        return self.binding


class FakeChannelDispatcharr:
    def __init__(self) -> None:
        self.create_calls = []
        self.update_calls = []
        self.created_channel = None
        self.updated_channel = None
        self.update_error = None

    def create_channel(
        self,
        *,
        name,
        stream_ids,
    ):
        self.create_calls.append(
            (
                name,
                tuple(stream_ids),
            )
        )

        assert self.created_channel is not None
        return self.created_channel

    def update_channel(
        self,
        *,
        channel_id,
        name=None,
        stream_ids=None,
    ):
        self.update_calls.append(
            (
                channel_id,
                name,
                tuple(stream_ids)
                if stream_ids is not None
                else None,
            )
        )

        if self.update_error is not None:
            raise self.update_error

        assert self.updated_channel is not None
        return self.updated_channel


def _channel_plan():
    from live_source_orchestration import (
        LiveSourceProvisioningPlan,
        ProvisioningSourceStreams,
    )

    return LiveSourceProvisioningPlan(
        source_id="thesportsdb-2475374",
        atlas_channel_id=(
            "sports-live-thesportsdb-2475374"
        ),
        name=(
            "Seattle Seahawks vs "
            "New England Patriots"
        ),
        provider="thesportsdb",
        provider_event_id="2475374",
        match_kind="team_pair",
        resource_source_ids=(
            "primary",
            "later",
        ),
        source_streams=(
            ProvisioningSourceStreams(
                source_id="primary",
                stream_ids=(302, 301),
            ),
            ProvisioningSourceStreams(
                source_id="later",
                stream_ids=(202, 201),
            ),
        ),
    )


def test_reconcile_dispatcharr_channel_creates_when_unbound() -> None:
    from dispatcharr_admin import (
        SafeDispatcharrChannel,
    )
    from live_source_orchestration import (
        reconcile_dispatcharr_channel,
    )

    plan = _channel_plan()
    dispatcharr = FakeChannelDispatcharr()
    bindings = FakeChannelBindings()

    dispatcharr.created_channel = (
        SafeDispatcharrChannel(
            channel_id=42,
            channel_uuid="uuid-42",
            name=plan.name,
            stream_ids=plan.stream_ids,
        )
    )

    channel, binding = (
        reconcile_dispatcharr_channel(
            plan=plan,
            dispatcharr=dispatcharr,
            bindings=bindings,
        )
    )

    assert bindings.resolve_calls == [
        plan.atlas_channel_id
    ]

    assert dispatcharr.create_calls == [
        (
            plan.name,
            plan.stream_ids,
        )
    ]

    assert dispatcharr.update_calls == []

    assert bindings.set_calls == [
        (
            plan.atlas_channel_id,
            42,
            "uuid-42",
        )
    ]

    assert channel.channel_id == 42
    assert (
        binding.dispatcharr_channel_id
        == 42
    )


def test_reconcile_dispatcharr_channel_updates_persisted_identity() -> None:
    from dispatcharr_admin import (
        SafeDispatcharrChannel,
    )
    from dispatcharr_channel_bindings import (
        DispatcharrChannelBinding,
    )
    from live_source_orchestration import (
        reconcile_dispatcharr_channel,
    )

    plan = _channel_plan()

    bindings = FakeChannelBindings(
        DispatcharrChannelBinding(
            atlas_channel_id=(
                plan.atlas_channel_id
            ),
            dispatcharr_channel_id=42,
            dispatcharr_channel_uuid=(
                "old-uuid"
            ),
        )
    )

    dispatcharr = FakeChannelDispatcharr()

    dispatcharr.updated_channel = (
        SafeDispatcharrChannel(
            channel_id=42,
            channel_uuid="new-uuid",
            name=plan.name,
            stream_ids=plan.stream_ids,
        )
    )

    channel, binding = (
        reconcile_dispatcharr_channel(
            plan=plan,
            dispatcharr=dispatcharr,
            bindings=bindings,
        )
    )

    assert dispatcharr.create_calls == []

    assert dispatcharr.update_calls == [
        (
            42,
            plan.name,
            plan.stream_ids,
        )
    ]

    assert bindings.set_calls == [
        (
            plan.atlas_channel_id,
            42,
            "new-uuid",
        )
    ]

    assert channel.channel_uuid == (
        "new-uuid"
    )
    assert (
        binding.dispatcharr_channel_uuid
        == "new-uuid"
    )


def test_reconcile_dispatcharr_channel_bound_404_fails_closed() -> None:
    from dispatcharr_admin import (
        DispatcharrChannelNotFoundError,
    )
    from dispatcharr_channel_bindings import (
        DispatcharrChannelBinding,
    )
    from live_source_orchestration import (
        reconcile_dispatcharr_channel,
    )

    plan = _channel_plan()

    original_binding = (
        DispatcharrChannelBinding(
            atlas_channel_id=(
                plan.atlas_channel_id
            ),
            dispatcharr_channel_id=42,
            dispatcharr_channel_uuid=(
                "uuid-42"
            ),
        )
    )

    bindings = FakeChannelBindings(
        original_binding
    )

    dispatcharr = FakeChannelDispatcharr()
    dispatcharr.update_error = (
        DispatcharrChannelNotFoundError(
            "Dispatcharr channel was not found."
        )
    )

    with pytest.raises(
        DispatcharrChannelNotFoundError,
        match="channel was not found",
    ):
        reconcile_dispatcharr_channel(
            plan=plan,
            dispatcharr=dispatcharr,
            bindings=bindings,
        )

    assert dispatcharr.update_calls == [
        (
            42,
            plan.name,
            plan.stream_ids,
        )
    ]

    assert dispatcharr.create_calls == []
    assert bindings.set_calls == []
    assert bindings.binding == (
        original_binding
    )


def test_reconcile_dispatcharr_channel_create_failure_does_not_persist() -> None:
    from dispatcharr_admin import (
        DispatcharrAdminError,
    )
    from live_source_orchestration import (
        reconcile_dispatcharr_channel,
    )

    plan = _channel_plan()
    bindings = FakeChannelBindings()

    class FailedCreate(
        FakeChannelDispatcharr
    ):
        def create_channel(
            self,
            *,
            name,
            stream_ids,
        ):
            self.create_calls.append(
                (
                    name,
                    tuple(stream_ids),
                )
            )
            raise DispatcharrAdminError(
                "create failed"
            )

    dispatcharr = FailedCreate()

    with pytest.raises(
        DispatcharrAdminError,
        match="create failed",
    ):
        reconcile_dispatcharr_channel(
            plan=plan,
            dispatcharr=dispatcharr,
            bindings=bindings,
        )

    assert bindings.set_calls == []


def test_reconcile_dispatcharr_channel_update_failure_does_not_mutate_binding() -> None:
    from dispatcharr_admin import (
        DispatcharrAdminError,
    )
    from dispatcharr_channel_bindings import (
        DispatcharrChannelBinding,
    )
    from live_source_orchestration import (
        reconcile_dispatcharr_channel,
    )

    plan = _channel_plan()

    original_binding = (
        DispatcharrChannelBinding(
            atlas_channel_id=(
                plan.atlas_channel_id
            ),
            dispatcharr_channel_id=42,
            dispatcharr_channel_uuid=(
                "uuid-42"
            ),
        )
    )

    bindings = FakeChannelBindings(
        original_binding
    )

    dispatcharr = FakeChannelDispatcharr()
    dispatcharr.update_error = (
        DispatcharrAdminError(
            "update failed"
        )
    )

    with pytest.raises(
        DispatcharrAdminError,
        match="update failed",
    ):
        reconcile_dispatcharr_channel(
            plan=plan,
            dispatcharr=dispatcharr,
            bindings=bindings,
        )

    assert dispatcharr.create_calls == []
    assert bindings.set_calls == []
    assert bindings.binding == (
        original_binding
    )



def test_build_published_live_source_uses_dispatcharr_channel_uuid() -> None:
    from dispatcharr_admin import SafeDispatcharrChannel
    from live_source_orchestration import (
        build_published_live_source,
    )

    plan = _channel_plan()

    channel = SafeDispatcharrChannel(
        channel_id=42,
        channel_uuid=(
            "00000000-0000-0000-0000-000000000042"
        ),
        name=plan.name,
        stream_ids=plan.stream_ids,
    )

    source = build_published_live_source(
        plan=plan,
        channel=channel,
        dispatcharr_base_url=(
            "http://atlas-dispatcharr:9191"
        ),
    )

    assert source.source_id == plan.source_id
    assert source.name == plan.name
    assert source.provider == plan.provider
    assert (
        source.provider_event_id
        == plan.provider_event_id
    )
    assert (
        source.resource_source_ids
        == plan.resource_source_ids
    )
    assert source.standalone is False
    assert (
        source.atlas_channel_id
        == plan.atlas_channel_id
    )
    assert source.stream_url == (
        "http://atlas-dispatcharr:9191/"
        "proxy/ts/stream/"
        "00000000-0000-0000-0000-000000000042"
    )


def test_build_published_live_source_preserves_dispatcharr_base_path() -> None:
    from dispatcharr_admin import SafeDispatcharrChannel
    from live_source_orchestration import (
        build_published_live_source,
    )

    plan = _channel_plan()

    source = build_published_live_source(
        plan=plan,
        channel=SafeDispatcharrChannel(
            channel_id=42,
            channel_uuid="uuid/needs-quoting",
            name=plan.name,
            stream_ids=plan.stream_ids,
        ),
        dispatcharr_base_url=(
            "https://dispatcharr.invalid/base/"
        ),
    )

    assert source.stream_url == (
        "https://dispatcharr.invalid/base/"
        "proxy/ts/stream/uuid%2Fneeds-quoting"
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "dispatcharr.invalid",
        "file:///tmp/dispatcharr",
        "https://user:pass@dispatcharr.invalid",
        "https://dispatcharr.invalid?token=secret",
        "https://dispatcharr.invalid/#fragment",
    ],
)
def test_build_published_live_source_rejects_unsafe_base_url(
    base_url,
) -> None:
    from dispatcharr_admin import SafeDispatcharrChannel
    from live_source_orchestration import (
        build_published_live_source,
    )

    plan = _channel_plan()

    with pytest.raises(
        ValueError,
        match="Dispatcharr base URL",
    ):
        build_published_live_source(
            plan=plan,
            channel=SafeDispatcharrChannel(
                channel_id=42,
                channel_uuid="uuid-42",
                name=plan.name,
                stream_ids=plan.stream_ids,
            ),
            dispatcharr_base_url=base_url,
        )
