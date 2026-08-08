"""Tests for Atlas Operations runtime-context contracts."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pytest

from atlas.operations import (
    HostOperationsContextProvider,
    OperationsContext,
    OperationsContextError,
    OperationsContextProvider,
)


class FakeHostnameProvider:
    """Deterministic hostname provider for context tests."""

    def hostname(self) -> str:
        return " Docker "


def completed(
    *,
    returncode: int = 0,
    stdout: str = "087D4322\n",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def context_provider(
    tmp_path: Path,
    *,
    hostname_provider: object | None = None,
    clock=None,
    executor=None,
) -> HostOperationsContextProvider:
    (tmp_path / "VERSION").write_text(
        " 0.9.0-rc.1 \n",
        encoding="utf-8",
    )

    return HostOperationsContextProvider(
        project_root=tmp_path,
        hostname_provider=(
            hostname_provider
            if hostname_provider is not None
            else FakeHostnameProvider()
        ),
        clock=(
            clock
            if clock is not None
            else lambda: datetime(
                2026,
                8,
                3,
                15,
                0,
                tzinfo=timezone.utc,
            )
        ),
        executor=(
            executor
            if executor is not None
            else lambda command, **kwargs: completed()
        ),
    )


def test_context_normalizes_report_metadata() -> None:
    result = OperationsContext(
        report_id=" Daily Operations ",
        hostname=" Docker ",
        atlas_version=" 0.9.0-rc.1 ",
        git_commit="087D4322",
        generated_at="2026-08-03T15:00:00-04:00",
    )

    assert result.report_id == "daily-operations"
    assert result.hostname == "docker"
    assert result.atlas_version == "0.9.0-rc.1"
    assert result.git_commit == "087d4322"
    assert result.generated_at == "2026-08-03T19:00:00Z"


def test_context_serialization_is_deterministic() -> None:
    result = OperationsContext(
        report_id="daily-operations",
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="087d4322",
        generated_at="2026-08-03T19:00:00Z",
    )

    assert result.to_dict() == {
        "report_id": "daily-operations",
        "hostname": "docker",
        "atlas_version": "0.9.0-rc.1",
        "git_commit": "087d4322",
        "generated_at": "2026-08-03T19:00:00Z",
    }


def test_context_rejects_invalid_model_contract() -> None:
    with pytest.raises(
        OperationsContextError,
        match="invalid Operations runtime context",
    ):
        OperationsContext(
            report_id="daily",
            hostname="docker",
            atlas_version="0.9.0",
            git_commit="invalid",
            generated_at="2026-08-03T19:00:00Z",
        )


def test_context_is_immutable() -> None:
    result = OperationsContext(
        report_id="daily",
        hostname="docker",
        atlas_version="0.9.0",
        git_commit="087d4322",
        generated_at="2026-08-03T19:00:00Z",
    )

    with pytest.raises(FrozenInstanceError):
        result.hostname = "changed"  # type: ignore[misc]


def test_host_provider_collects_runtime_context(
    tmp_path: Path,
) -> None:
    calls: list[tuple[object, dict[str, object]]] = []

    def executor(command, **kwargs):
        calls.append((command, kwargs))
        return completed()

    result = context_provider(
        tmp_path,
        executor=executor,
    ).context(
        report_id="daily-operations",
    )

    assert result.to_dict() == {
        "report_id": "daily-operations",
        "hostname": "docker",
        "atlas_version": "0.9.0-rc.1",
        "git_commit": "087d4322",
        "generated_at": "2026-08-03T15:00:00Z",
    }

    assert calls == [
        (
            [
                "git",
                "rev-parse",
                "--short",
                "HEAD",
            ],
            {
                "cwd": tmp_path,
                "capture_output": True,
                "text": True,
                "check": False,
            },
        ),
    ]


def test_host_provider_uses_default_report_id(
    tmp_path: Path,
) -> None:
    result = context_provider(tmp_path).context()

    assert result.report_id == "operations-report"


def test_host_provider_rejects_missing_version(
    tmp_path: Path,
) -> None:
    provider = HostOperationsContextProvider(
        project_root=tmp_path,
        hostname_provider=FakeHostnameProvider(),
        clock=lambda: datetime.now(timezone.utc),
        executor=lambda command, **kwargs: completed(),
    )

    with pytest.raises(
        OperationsContextError,
        match="Atlas version could not be read",
    ):
        provider.context()


def test_host_provider_rejects_empty_version(
    tmp_path: Path,
) -> None:
    (tmp_path / "VERSION").write_text(
        " \n",
        encoding="utf-8",
    )

    provider = HostOperationsContextProvider(
        project_root=tmp_path,
        hostname_provider=FakeHostnameProvider(),
        clock=lambda: datetime.now(timezone.utc),
        executor=lambda command, **kwargs: completed(),
    )

    with pytest.raises(
        OperationsContextError,
        match="Atlas version file is empty",
    ):
        provider.context()


def test_host_provider_rejects_git_failure(
    tmp_path: Path,
) -> None:
    provider = context_provider(
        tmp_path,
        executor=lambda command, **kwargs: completed(
            returncode=128,
            stdout="",
            stderr="not a git repository",
        ),
    )

    with pytest.raises(
        OperationsContextError,
        match="Git commit discovery failed",
    ):
        provider.context()


def test_host_provider_rejects_invalid_git_result(
    tmp_path: Path,
) -> None:
    provider = context_provider(
        tmp_path,
        executor=lambda command, **kwargs: object(),
    )

    with pytest.raises(
        OperationsContextError,
        match="invalid result",
    ):
        provider.context()


def test_host_provider_requires_aware_clock(
    tmp_path: Path,
) -> None:
    provider = context_provider(
        tmp_path,
        clock=lambda: datetime(2026, 8, 3, 15, 0),
    )

    with pytest.raises(
        OperationsContextError,
        match="timezone-aware",
    ):
        provider.context()


def test_host_provider_rejects_invalid_dependencies() -> None:
    with pytest.raises(
        OperationsContextError,
        match=r"hostname_provider must define hostname\(\)",
    ):
        HostOperationsContextProvider(
            hostname_provider=object(),
        )

    with pytest.raises(
        OperationsContextError,
        match="clock must be callable",
    ):
        HostOperationsContextProvider(
            clock=None,  # type: ignore[arg-type]
        )

    with pytest.raises(
        OperationsContextError,
        match="executor must be callable",
    ):
        HostOperationsContextProvider(
            executor=None,  # type: ignore[arg-type]
        )


def test_public_context_exports() -> None:
    from atlas import operations

    assert operations.OperationsContext is OperationsContext
    assert (
        operations.OperationsContextProvider
        is OperationsContextProvider
    )
    assert (
        operations.HostOperationsContextProvider
        is HostOperationsContextProvider
    )
    assert (
        operations.OperationsContextError
        is OperationsContextError
    )


# M-023.24.5 Operations project-root portability


def test_host_provider_uses_configured_project_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_PROJECT_DIR",
        str(tmp_path),
    )

    provider = HostOperationsContextProvider()

    assert provider.project_root == tmp_path


def test_host_provider_defaults_to_production_project_root(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "ATLAS_PROJECT_DIR",
        raising=False,
    )

    provider = HostOperationsContextProvider()

    assert provider.project_root == Path(
        "/opt/project-atlas"
    )


def test_host_provider_rejects_empty_project_root(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_PROJECT_DIR",
        "   ",
    )

    with pytest.raises(
        OperationsContextError,
        match="ATLAS_PROJECT_DIR cannot be empty",
    ):
        HostOperationsContextProvider()
