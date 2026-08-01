"""Contract tests for the read-only Docker Compose provider foundation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from atlas.service_lifecycle import (
    DockerComposeProvider,
    DockerComposeProviderError,
    ManagedService,
    ServiceImage,
    ServiceLifecycleProvider,
    ServiceRuntime,
)


def make_compose_file(
    tmp_path: Path,
    *,
    name: str = "compose.yml",
) -> Path:
    path = tmp_path / name
    path.write_text(
        "services:\n"
        "  sonarr:\n"
        "    image: sonarr:latest\n",
        encoding="utf-8",
    )
    return path


def make_provider(
    tmp_path: Path,
    **overrides: object,
) -> DockerComposeProvider:
    compose_file = make_compose_file(tmp_path)

    values: dict[str, object] = {
        "compose_file": compose_file,
    }
    values.update(overrides)

    return DockerComposeProvider(**values)


def test_provider_implements_service_lifecycle_contract(
    tmp_path: Path,
) -> None:
    provider = make_provider(tmp_path)

    assert isinstance(
        provider,
        ServiceLifecycleProvider,
    )


def test_provider_normalizes_paths_and_timeout(
    tmp_path: Path,
) -> None:
    compose_file = make_compose_file(tmp_path)
    project_directory = tmp_path / "project"
    project_directory.mkdir()

    provider = DockerComposeProvider(
        compose_file=compose_file,
        project_directory=project_directory,
        timeout=5,
    )

    assert provider.compose_file == compose_file.resolve()
    assert provider.project_directory == project_directory.resolve()
    assert provider.timeout == 5.0


def test_provider_defaults_project_directory_to_compose_parent(
    tmp_path: Path,
) -> None:
    compose_file = make_compose_file(tmp_path)

    provider = DockerComposeProvider(
        compose_file=compose_file,
    )

    assert provider.project_directory == tmp_path.resolve()


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        42,
        object(),
    ],
)
def test_provider_rejects_invalid_compose_file_type(
    value: object,
) -> None:
    with pytest.raises(
        DockerComposeProviderError,
        match="compose_file must be a path",
    ):
        DockerComposeProvider(
            compose_file=value,  # type: ignore[arg-type]
        )


def test_provider_rejects_missing_compose_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        DockerComposeProviderError,
        match="compose_file does not exist",
    ):
        DockerComposeProvider(
            compose_file=tmp_path / "missing.yml",
        )


@pytest.mark.parametrize(
    "name",
    [
        "compose.txt",
        "compose.json",
        "compose",
    ],
)
def test_provider_requires_yaml_compose_file(
    tmp_path: Path,
    name: str,
) -> None:
    path = make_compose_file(
        tmp_path,
        name=name,
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="compose_file must use a .yml or .yaml extension",
    ):
        DockerComposeProvider(
            compose_file=path,
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        42,
        object(),
    ],
)
def test_provider_rejects_invalid_project_directory_type(
    tmp_path: Path,
    value: object,
) -> None:
    compose_file = make_compose_file(tmp_path)

    with pytest.raises(
        DockerComposeProviderError,
        match="project_directory must be a path or null",
    ):
        DockerComposeProvider(
            compose_file=compose_file,
            project_directory=value,  # type: ignore[arg-type]
        )


def test_provider_rejects_missing_project_directory(
    tmp_path: Path,
) -> None:
    compose_file = make_compose_file(tmp_path)

    with pytest.raises(
        DockerComposeProviderError,
        match="project_directory does not exist",
    ):
        DockerComposeProvider(
            compose_file=compose_file,
            project_directory=tmp_path / "missing",
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        True,
        None,
        "15",
        object(),
    ],
)
def test_provider_requires_positive_numeric_timeout(
    tmp_path: Path,
    value: object,
) -> None:
    compose_file = make_compose_file(tmp_path)

    with pytest.raises(
        DockerComposeProviderError,
        match="timeout must be a positive number",
    ):
        DockerComposeProvider(
            compose_file=compose_file,
            timeout=value,  # type: ignore[arg-type]
        )


def test_provider_copies_environment_mapping(
    tmp_path: Path,
) -> None:
    environment = {
        "PATH": "/usr/bin",
    }

    provider = make_provider(
        tmp_path,
        environment=environment,
    )

    environment["PATH"] = "/changed"

    assert provider.environment == {
        "PATH": "/usr/bin",
    }


@pytest.mark.parametrize(
    "value",
    [
        "PATH=/usr/bin",
        42,
        True,
        object(),
    ],
)
def test_provider_requires_environment_mapping(
    tmp_path: Path,
    value: object,
) -> None:
    with pytest.raises(
        DockerComposeProviderError,
        match="environment must be an object or null",
    ):
        make_provider(
            tmp_path,
            environment=value,
        )


@pytest.mark.parametrize(
    "environment",
    [
        {
            "": "value",
        },
        {
            "   ": "value",
        },
        {
            42: "value",
        },
        {
            "KEY": 42,
        },
    ],
)
def test_provider_requires_string_environment_entries(
    tmp_path: Path,
    environment: dict[object, object],
) -> None:
    with pytest.raises(
        DockerComposeProviderError,
        match="environment must contain string keys and values",
    ):
        make_provider(
            tmp_path,
            environment=environment,
        )


def test_provider_repr_hides_environment_values(
    tmp_path: Path,
) -> None:
    provider = make_provider(
        tmp_path,
        environment={
            "SECRET_TOKEN": "hidden-value",
        },
    )

    rendered = repr(provider)

    assert "SECRET_TOKEN" not in rendered
    assert "hidden-value" not in rendered


def test_build_compose_command_uses_fixed_arguments(
    tmp_path: Path,
) -> None:
    provider = make_provider(tmp_path)

    command = provider._build_compose_command(
        "config",
        "--services",
    )

    assert command == (
        "docker",
        "compose",
        "--file",
        str(provider.compose_file),
        "--project-directory",
        str(provider.project_directory),
        "config",
        "--services",
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        True,
        42,
        object(),
    ],
)
def test_build_compose_command_rejects_invalid_argument(
    tmp_path: Path,
    value: object,
) -> None:
    provider = make_provider(tmp_path)

    with pytest.raises(
        DockerComposeProviderError,
        match="Compose arguments must be non-empty strings",
    ):
        provider._build_compose_command(
            value,  # type: ignore[arg-type]
        )


def test_build_compose_command_rejects_null_byte(
    tmp_path: Path,
) -> None:
    provider = make_provider(tmp_path)

    with pytest.raises(
        DockerComposeProviderError,
        match="must not contain null bytes",
    ):
        provider._build_compose_command(
            "config\x00services",
        )


def test_run_compose_uses_shell_false_and_expected_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(
        tmp_path,
        timeout=7,
        environment={
            "PATH": "/usr/bin",
        },
    )

    captured: dict[str, object] = {}

    def fake_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(kwargs)

        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout="sonarr\n",
            stderr="",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    result = provider._run_compose(
        "config",
        "--services",
    )

    assert result.stdout == "sonarr\n"
    assert captured["shell"] is False
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["check"] is False
    assert captured["timeout"] == 7.0
    assert captured["cwd"] == provider.project_directory
    assert captured["env"] == {
        "PATH": "/usr/bin",
    }


def test_run_compose_uses_inherited_environment_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    captured: dict[str, object] = {}

    def fake_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)

        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    provider._run_compose(
        "version",
    )

    assert captured["env"] is None


def test_run_compose_translates_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    def fake_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            command,
            timeout=15,
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="inspection timed out",
    ):
        provider._run_compose(
            "config",
        )


def test_run_compose_translates_missing_docker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    def fake_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("docker")

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Docker executable was not found",
    ):
        provider._run_compose(
            "config",
        )


def test_run_compose_translates_os_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    def fake_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise OSError("failed")

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="could not be started",
    ):
        provider._run_compose(
            "config",
        )


def test_run_compose_translates_nonzero_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    def fake_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            returncode=1,
            stdout="",
            stderr=" compose failed \n",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Docker Compose inspection failed: compose failed",
    ):
        provider._run_compose(
            "config",
        )


def test_run_compose_truncates_diagnostic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)
    diagnostic = "x" * 700

    def fake_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            returncode=1,
            stdout="",
            stderr=diagnostic,
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        DockerComposeProviderError,
    ) as exc_info:
        provider._run_compose(
            "config",
        )

    assert len(str(exc_info.value)) <= 550


def test_run_compose_json_decodes_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose",
        lambda self, *arguments: SimpleNamespace(
            stdout='{"services": {"sonarr": {}}}',
        ),
    )

    assert provider._run_compose_json(
        "config",
        "--format",
        "json",
    ) == {
        "services": {
            "sonarr": {},
        },
    }


def test_run_compose_json_rejects_empty_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose",
        lambda self, *arguments: SimpleNamespace(
            stdout="   ",
        ),
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="empty JSON response",
    ):
        provider._run_compose_json(
            "config",
        )


def test_run_compose_json_rejects_invalid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose",
        lambda self, *arguments: SimpleNamespace(
            stdout="{invalid",
        ),
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="returned invalid JSON",
    ):
        provider._run_compose_json(
            "config",
        )


def test_list_services_normalizes_compose_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    payload = {
        "name": "project-atlas",
        "services": {
            "sonarr-anime": {
                "container_name": " sonarr-anime ",
                "depends_on": {
                    "prowlarr": {
                        "condition": "service_started",
                    },
                    "gluetun": {
                        "condition": "service_healthy",
                    },
                },
            },
            "prowlarr": {
                "container_name": "prowlarr",
            },
        },
    }

    captured: list[tuple[str, ...]] = []

    def fake_run_compose_json(
        self: DockerComposeProvider,
        *arguments: str,
    ) -> object:
        captured.append(arguments)
        return payload

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        fake_run_compose_json,
    )

    services = provider.list_services()

    assert captured == [
        (
            "config",
            "--format",
            "json",
        ),
    ]

    assert tuple(
        service.identifier
        for service in services
    ) == (
        "prowlarr",
        "sonarr-anime",
    )

    by_identifier = {
        service.identifier: service
        for service in services
    }

    sonarr = by_identifier["sonarr-anime"]

    assert sonarr.name == "Sonarr Anime"
    assert sonarr.provider == "docker-compose"
    assert sonarr.enabled is True
    assert sonarr.compose_project == "project-atlas"
    assert sonarr.container_name == "sonarr-anime"
    assert sonarr.dependencies == (
        "gluetun",
        "prowlarr",
    )

    prowlarr = by_identifier["prowlarr"]

    assert prowlarr.name == "Prowlarr"
    assert prowlarr.dependencies == ()


def test_list_services_uses_project_directory_name_as_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "services": {
                "sonarr": {},
            },
        },
    )

    services = provider.list_services()

    assert len(services) == 1
    assert services[0].compose_project == tmp_path.name


def test_list_services_accepts_sequence_dependencies(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": {
                "jellyseerr": {
                    "depends_on": [
                        " Sonarr ",
                        "radarr",
                        "sonarr",
                    ],
                },
            },
        },
    )

    services = provider.list_services()

    assert services[0].dependencies == (
        "radarr",
        "sonarr",
    )


def test_list_services_sorts_by_display_name_then_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": {
                "sonarr-anime": {},
                "bazarr": {},
                "sonarr": {},
                "radarr": {},
            },
        },
    )

    services = provider.list_services()

    assert tuple(
        service.identifier
        for service in services
    ) == (
        "bazarr",
        "radarr",
        "sonarr",
        "sonarr-anime",
    )


def test_list_services_supports_underscored_service_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": {
                "media_request": {},
            },
        },
    )

    service = provider.list_services()[0]

    assert service.identifier == "media_request"
    assert service.name == "Media Request"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "services",
        42,
        True,
    ],
)
def test_list_services_requires_configuration_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: payload,
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="configuration must be an object",
    ):
        provider.list_services()


@pytest.mark.parametrize(
    "services",
    [
        None,
        [],
        "sonarr",
        42,
        True,
    ],
)
def test_list_services_requires_services_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    services: object,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": services,
        },
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="must contain a services object",
    ):
        provider.list_services()


@pytest.mark.parametrize(
    "project_name",
    [
        "",
        "   ",
        True,
        42,
        object(),
    ],
)
def test_list_services_requires_valid_project_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    project_name: object,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": project_name,
            "services": {},
        },
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="project name must be non-empty text",
    ):
        provider.list_services()


@pytest.mark.parametrize(
    "identifier",
    [
        "",
        "   ",
        42,
        True,
        None,
    ],
)
def test_list_services_requires_string_service_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identifier: object,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": {
                identifier: {},
            },
        },
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="service identifiers must be non-empty strings",
    ):
        provider.list_services()


@pytest.mark.parametrize(
    "configuration",
    [
        None,
        [],
        "configuration",
        42,
        True,
    ],
)
def test_list_services_requires_service_configuration_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: object,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": {
                "sonarr": configuration,
            },
        },
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="service configuration must be an object",
    ):
        provider.list_services()


@pytest.mark.parametrize(
    "container_name",
    [
        "",
        "   ",
        True,
        42,
        object(),
    ],
)
def test_list_services_rejects_invalid_container_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    container_name: object,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": {
                "sonarr": {
                    "container_name": container_name,
                },
            },
        },
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="container_name must be non-empty text or null",
    ):
        provider.list_services()


@pytest.mark.parametrize(
    "depends_on",
    [
        "prowlarr",
        42,
        True,
        object(),
    ],
)
def test_list_services_rejects_invalid_dependencies_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    depends_on: object,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": {
                "sonarr": {
                    "depends_on": depends_on,
                },
            },
        },
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="depends_on must be an object, a collection, or null",
    ):
        provider.list_services()


@pytest.mark.parametrize(
    "dependency",
    [
        "",
        "   ",
        None,
        True,
        42,
        object(),
    ],
)
def test_list_services_rejects_invalid_dependency_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dependency: object,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": {
                "sonarr": {
                    "depends_on": [
                        dependency,
                    ],
                },
            },
        },
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="dependencies must contain non-empty service identifiers",
    ):
        provider.list_services()


def test_list_services_translates_managed_service_validation_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose_json",
        lambda self, *arguments: {
            "name": "atlas",
            "services": {
                "invalid/service": {},
            },
        },
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Invalid Compose service configuration",
    ):
        provider.list_services()



def test_inspect_service_normalizes_requested_identifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "list_services",
        lambda self: (
            ManagedService(
                identifier="sonarr-anime",
                name="Sonarr Anime",
                provider="docker-compose",
                compose_project="atlas",
                container_name="sonarr-anime",
                dependencies=(
                    "prowlarr",
                ),
            ),
        ),
    )

    service = provider.inspect_service(
        "  SONARR-ANIME  ",
    )

    assert service.identifier == "sonarr-anime"
    assert service.name == "Sonarr Anime"
    assert service.container_name == "sonarr-anime"
    assert service.dependencies == (
        "prowlarr",
    )


def test_inspect_service_reuses_list_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)
    calls: list[str] = []

    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )

    def fake_list_services(
        self: DockerComposeProvider,
    ) -> tuple[ManagedService, ...]:
        calls.append("list_services")
        return (
            service,
        )

    monkeypatch.setattr(
        DockerComposeProvider,
        "list_services",
        fake_list_services,
    )

    result = provider.inspect_service("sonarr")

    assert result is service
    assert calls == [
        "list_services",
    ]


def test_inspect_service_returns_exact_matching_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    sonarr = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )
    sonarr_anime = ManagedService(
        identifier="sonarr-anime",
        name="Sonarr Anime",
        provider="docker-compose",
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "list_services",
        lambda self: (
            sonarr,
            sonarr_anime,
        ),
    )

    assert provider.inspect_service("sonarr") is sonarr
    assert (
        provider.inspect_service("sonarr-anime")
        is sonarr_anime
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        True,
        42,
        object(),
    ],
)
def test_inspect_service_requires_non_empty_text_identifier(
    tmp_path: Path,
    value: object,
) -> None:
    provider = make_provider(tmp_path)

    with pytest.raises(
        DockerComposeProviderError,
        match="service identifier must be non-empty text",
    ):
        provider.inspect_service(
            value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        "-sonarr",
        "sonarr-",
        ".sonarr",
        "sonarr.",
        "son arr",
        "sonarr/api",
        "sonarr:latest",
        "sonarr@atlas",
    ],
)
def test_inspect_service_rejects_malformed_identifier(
    tmp_path: Path,
    value: str,
) -> None:
    provider = make_provider(tmp_path)

    with pytest.raises(
        DockerComposeProviderError,
        match="invalid service identifier",
    ):
        provider.inspect_service(value)


def test_inspect_service_reports_unknown_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "list_services",
        lambda self: (
            ManagedService(
                identifier="sonarr",
                name="Sonarr",
                provider="docker-compose",
            ),
        ),
    )

    with pytest.raises(
        DockerComposeProviderError,
        match=(
            "Docker Compose service was not found: prowlarr"
        ),
    ):
        provider.inspect_service(
            "  PROWLARR  ",
        )


def test_inspect_service_returns_managed_service_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    expected = ManagedService(
        identifier="qbittorrent",
        name="Qbittorrent",
        provider="docker-compose",
        compose_project="atlas",
        container_name="qbittorrent",
        dependencies=(
            "gluetun",
        ),
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "list_services",
        lambda self: (
            expected,
        ),
    )

    result = provider.inspect_service(
        "qbittorrent",
    )

    assert result is expected
    assert isinstance(
        result,
        ManagedService,
    )



def make_runtime_inspect_payload(
    **overrides: object,
) -> list[object]:
    container: dict[str, object] = {
        "Image": "sha256:" + ("a" * 64),
        "RestartCount": 2,
        "Config": {
            "Image": "lscr.io/linuxserver/sonarr:latest",
        },
        "State": {
            "Status": "running",
            "Running": True,
            "Paused": False,
            "Restarting": False,
            "Dead": False,
            "ExitCode": 0,
            "Error": "",
            "StartedAt": "2026-08-01T12:00:00Z",
            "FinishedAt": "0001-01-01T00:00:00Z",
            "Health": {
                "Status": "healthy",
            },
        },
    }

    container.update(overrides)

    return [
        container,
    ]


def test_inspect_runtime_normalizes_live_container_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
        compose_project="atlas",
        container_name="sonarr",
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_service",
        lambda self, identifier: service,
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_resolve_container_identifier",
        lambda self, value: "container-id",
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker_json",
        lambda self, *arguments: make_runtime_inspect_payload(),
    )

    runtime = provider.inspect_runtime(" SONARR ")

    assert isinstance(runtime, ServiceRuntime)
    assert runtime.state == "running"
    assert runtime.health == "healthy"
    assert runtime.running is True
    assert runtime.healthy is True
    assert runtime.restart_count == 2
    assert runtime.started_at == "2026-08-01T12:00:00Z"
    assert runtime.finished_at is None
    assert runtime.exit_code == 0
    assert runtime.status_message == "running"

    assert isinstance(runtime.image, ServiceImage)
    assert runtime.image.reference == (
        "lscr.io/linuxserver/sonarr:latest"
    )
    assert runtime.image.repository == (
        "lscr.io/linuxserver/sonarr"
    )
    assert runtime.image.tag == "latest"
    assert runtime.image.digest is None
    assert runtime.image.image_id == (
        "sha256:" + ("a" * 64)
    )


def test_inspect_runtime_uses_expected_provider_operations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)
    calls: list[object] = []

    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )

    def fake_inspect_service(
        self: DockerComposeProvider,
        identifier: str,
    ) -> ManagedService:
        calls.append(
            (
                "inspect_service",
                identifier,
            )
        )
        return service

    def fake_resolve(
        self: DockerComposeProvider,
        value: ManagedService,
    ) -> str:
        calls.append(
            (
                "resolve",
                value,
            )
        )
        return "container-id"

    def fake_run_docker_json(
        self: DockerComposeProvider,
        *arguments: str,
    ) -> object:
        calls.append(
            (
                "docker",
                arguments,
            )
        )
        return make_runtime_inspect_payload()

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_service",
        fake_inspect_service,
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_resolve_container_identifier",
        fake_resolve,
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker_json",
        fake_run_docker_json,
    )

    provider.inspect_runtime("sonarr")

    assert calls == [
        (
            "inspect_service",
            "sonarr",
        ),
        (
            "resolve",
            service,
        ),
        (
            "docker",
            (
                "inspect",
                "container-id",
            ),
        ),
    ]


def test_resolve_container_identifier_uses_compose_ps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)
    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )
    captured: list[tuple[str, ...]] = []

    def fake_run_compose(
        self: DockerComposeProvider,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        captured.append(arguments)

        return subprocess.CompletedProcess(
            arguments,
            returncode=0,
            stdout=" container-id \n",
            stderr="",
        )

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose",
        fake_run_compose,
    )

    result = provider._resolve_container_identifier(
        service,
    )

    assert result == "container-id"
    assert captured == [
        (
            "ps",
            "--all",
            "--quiet",
            "sonarr",
        ),
    ]


def test_resolve_container_identifier_requires_managed_service(
    tmp_path: Path,
) -> None:
    provider = make_provider(tmp_path)

    with pytest.raises(
        DockerComposeProviderError,
        match="service must be a ManagedService",
    ):
        provider._resolve_container_identifier(
            "sonarr",  # type: ignore[arg-type]
        )


def test_resolve_container_identifier_rejects_missing_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)
    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose",
        lambda self, *arguments: subprocess.CompletedProcess(
            arguments,
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Docker Compose container was not found: sonarr",
    ):
        provider._resolve_container_identifier(service)


def test_resolve_container_identifier_rejects_multiple_containers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)
    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_compose",
        lambda self, *arguments: subprocess.CompletedProcess(
            arguments,
            returncode=0,
            stdout="container-one\ncontainer-two\n",
            stderr="",
        ),
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Docker Compose returned multiple containers: sonarr",
    ):
        provider._resolve_container_identifier(service)


def test_build_docker_command_uses_fixed_arguments(
    tmp_path: Path,
) -> None:
    provider = make_provider(tmp_path)

    assert provider._build_docker_command(
        "inspect",
        "container-id",
    ) == (
        "docker",
        "inspect",
        "container-id",
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        True,
        42,
        object(),
    ],
)
def test_build_docker_command_rejects_invalid_argument(
    tmp_path: Path,
    value: object,
) -> None:
    provider = make_provider(tmp_path)

    with pytest.raises(
        DockerComposeProviderError,
        match="Compose arguments must be non-empty strings",
    ):
        provider._build_docker_command(
            value,  # type: ignore[arg-type]
        )


def test_run_docker_uses_shell_false_and_expected_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(
        tmp_path,
        timeout=8,
        environment={
            "PATH": "/usr/bin",
        },
    )
    captured: dict[str, object] = {}

    def fake_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(kwargs)

        return subprocess.CompletedProcess(
            command,
            returncode=0,
            stdout="[]",
            stderr="",
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    provider._run_docker(
        "inspect",
        "container-id",
    )

    assert captured["command"] == (
        "docker",
        "inspect",
        "container-id",
    )
    assert captured["shell"] is False
    assert captured["capture_output"] is True
    assert captured["text"] is True
    assert captured["check"] is False
    assert captured["timeout"] == 8.0
    assert captured["cwd"] == provider.project_directory
    assert captured["env"] == {
        "PATH": "/usr/bin",
    }


def test_run_docker_translates_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    def fake_run(
        command: tuple[str, ...],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            command,
            timeout=15,
        )

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Docker inspection timed out",
    ):
        provider._run_docker(
            "inspect",
            "container-id",
        )


def test_run_docker_translates_nonzero_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            returncode=1,
            stdout="",
            stderr="container not found",
        ),
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Docker inspection failed: container not found",
    ):
        provider._run_docker(
            "inspect",
            "container-id",
        )


def test_run_docker_json_decodes_inspection_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker",
        lambda self, *arguments: SimpleNamespace(
            stdout='[{"State": {}, "Config": {}}]',
        ),
    )

    assert provider._run_docker_json(
        "inspect",
        "container-id",
    ) == [
        {
            "State": {},
            "Config": {},
        },
    ]


@pytest.mark.parametrize(
    "output",
    [
        "",
        "   ",
    ],
)
def test_run_docker_json_rejects_empty_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: str,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker",
        lambda self, *arguments: SimpleNamespace(
            stdout=output,
        ),
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Docker returned an empty JSON response",
    ):
        provider._run_docker_json(
            "inspect",
            "container-id",
        )


def test_run_docker_json_rejects_invalid_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)

    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker",
        lambda self, *arguments: SimpleNamespace(
            stdout="{invalid",
        ),
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Docker returned invalid JSON",
    ):
        provider._run_docker_json(
            "inspect",
            "container-id",
        )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        "container",
        42,
        True,
    ],
)
def test_inspect_runtime_requires_inspection_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: object,
) -> None:
    provider = make_provider(tmp_path)
    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_service",
        lambda self, identifier: service,
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_resolve_container_identifier",
        lambda self, value: "container-id",
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker_json",
        lambda self, *arguments: payload,
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="Docker inspect response must be a collection",
    ):
        provider.inspect_runtime("sonarr")


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [
            {},
            {},
        ],
    ],
)
def test_inspect_runtime_requires_exactly_one_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: list[object],
) -> None:
    provider = make_provider(tmp_path)
    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_service",
        lambda self, identifier: service,
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_resolve_container_identifier",
        lambda self, value: "container-id",
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker_json",
        lambda self, *arguments: payload,
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="must contain exactly one object",
    ):
        provider.inspect_runtime("sonarr")


def test_inspect_runtime_normalizes_missing_health_as_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)
    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )
    payload = make_runtime_inspect_payload()

    container = payload[0]
    assert isinstance(container, dict)

    state = container["State"]
    assert isinstance(state, dict)
    state.pop("Health")

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_service",
        lambda self, identifier: service,
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_resolve_container_identifier",
        lambda self, value: "container-id",
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker_json",
        lambda self, *arguments: payload,
    )

    runtime = provider.inspect_runtime("sonarr")

    assert runtime.health == "unknown"
    assert runtime.healthy is False


@pytest.mark.parametrize(
    ("state_updates", "expected"),
    [
        (
            {
                "Status": "running",
                "Paused": True,
            },
            "paused",
        ),
        (
            {
                "Status": "running",
                "Restarting": True,
            },
            "restarting",
        ),
        (
            {
                "Status": "exited",
                "Dead": True,
            },
            "dead",
        ),
        (
            {
                "Status": "exited",
            },
            "exited",
        ),
    ],
)
def test_inspect_runtime_normalizes_runtime_state_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    state_updates: dict[str, object],
    expected: str,
) -> None:
    provider = make_provider(tmp_path)
    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )
    payload = make_runtime_inspect_payload()

    container = payload[0]
    assert isinstance(container, dict)

    state = container["State"]
    assert isinstance(state, dict)
    state.update(state_updates)

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_service",
        lambda self, identifier: service,
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_resolve_container_identifier",
        lambda self, value: "container-id",
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker_json",
        lambda self, *arguments: payload,
    )

    runtime = provider.inspect_runtime("sonarr")

    assert runtime.state == expected


def test_inspect_runtime_normalizes_digest_image_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = make_provider(tmp_path)
    service = ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )
    digest = "sha256:" + ("b" * 64)
    payload = make_runtime_inspect_payload(
        Config={
            "Image": (
                "lscr.io/linuxserver/sonarr@"
                f"{digest}"
            ),
        },
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_service",
        lambda self, identifier: service,
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_resolve_container_identifier",
        lambda self, value: "container-id",
    )
    monkeypatch.setattr(
        DockerComposeProvider,
        "_run_docker_json",
        lambda self, *arguments: payload,
    )

    runtime = provider.inspect_runtime("sonarr")

    assert runtime.image.repository == (
        "lscr.io/linuxserver/sonarr"
    )
    assert runtime.image.tag is None
    assert runtime.image.digest == digest


@pytest.mark.parametrize(
    "method_name",
    [
        "inspect_health",
    ],
)
def test_read_only_provider_methods_remain_explicitly_pending(
    tmp_path: Path,
    method_name: str,
) -> None:
    provider = make_provider(tmp_path)
    method = getattr(
        provider,
        method_name,
    )

    arguments = (
        ()
        if method_name == "list_services"
        else ("sonarr",)
    )

    with pytest.raises(
        DockerComposeProviderError,
        match="not implemented yet",
    ):
        method(*arguments)


def test_package_exports_docker_compose_provider() -> None:
    from atlas import service_lifecycle

    assert (
        service_lifecycle.DockerComposeProvider
        is DockerComposeProvider
    )
    assert (
        service_lifecycle.DockerComposeProviderError
        is DockerComposeProviderError
    )
