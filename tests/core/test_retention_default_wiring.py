from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import atlas.retention as retention_public
import atlas.retention.service as retention_service_module
from atlas import retention_cli
from atlas.cleanup import service as cleanup_service_module
from atlas.policies import (
    PolicyAction,
    PolicyDecision,
)
from atlas.retention import RetentionDecision


class FakeProvider:
    pass


class FakeUserStore:
    pass


def test_default_retention_factory_wires_jellyfin_and_users(
    monkeypatch,
) -> None:
    provider = FakeProvider()
    users = FakeUserStore()

    monkeypatch.setattr(
        retention_service_module,
        "default_jellyfin_provider",
        lambda: provider,
        raising=False,
    )

    monkeypatch.setattr(
        retention_service_module,
        "default_user_store",
        lambda: users,
        raising=False,
    )

    service = (
        retention_service_module
        .default_retention_service()
    )

    assert service.media_providers == {
        "jellyfin": provider,
    }
    assert service.user_store is users


def test_default_retention_factory_is_public() -> None:
    assert callable(
        retention_public.default_retention_service
    )


def test_cleanup_service_uses_default_retention_factory(
    monkeypatch,
) -> None:
    sentinel = object()
    calls: list[str] = []

    def factory():
        calls.append("default")
        return sentinel

    monkeypatch.setattr(
        cleanup_service_module,
        "default_retention_service",
        factory,
        raising=False,
    )

    service = cleanup_service_module.CleanupService()

    assert calls == ["default"]
    assert service._retention_service is sentinel


def test_explicit_cleanup_retention_service_is_preserved(
    monkeypatch,
) -> None:
    sentinel = object()

    def factory():
        raise AssertionError(
            "default factory must not run "
            "when dependency is explicit"
        )

    monkeypatch.setattr(
        cleanup_service_module,
        "default_retention_service",
        factory,
        raising=False,
    )

    service = cleanup_service_module.CleanupService(
        retention_service=sentinel,
    )

    assert service._retention_service is sentinel


class FakeCliRetentionService:
    def __init__(self) -> None:
        self.calls: list[
            tuple[str, str]
        ] = []

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> RetentionDecision:
        self.calls.append(
            (
                provider,
                item_id,
            )
        )

        policy = PolicyDecision(
            provider=provider,
            item_id=item_id,
            action=PolicyAction.IGNORE,
        )

        return RetentionDecision(
            provider=provider,
            item_id=item_id,
            eligible=False,
            policy=policy,
        )


def test_retention_cli_uses_default_retention_factory(
    monkeypatch,
) -> None:
    service = FakeCliRetentionService()
    factory_calls: list[str] = []

    def factory():
        factory_calls.append("default")
        return service

    monkeypatch.setattr(
        retention_cli,
        "default_retention_service",
        factory,
        raising=False,
    )

    class ForbiddenRetentionService:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError(
                "CLI must use default_retention_service"
            )

    monkeypatch.setattr(
        retention_cli,
        "RetentionService",
        ForbiddenRetentionService,
    )

    with patch(
        "sys.stdout",
        new_callable=StringIO,
    ):
        result = retention_cli.main(
            [
                "evaluate",
                "jellyfin",
                "movie-1",
                "--json",
            ]
        )

    assert result == 0
    assert factory_calls == ["default"]
    assert service.calls == [
        (
            "jellyfin",
            "movie-1",
        )
    ]
