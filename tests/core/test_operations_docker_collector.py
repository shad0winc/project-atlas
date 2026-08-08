"""Tests for the Atlas Docker command-adapter contract."""

import pytest

from atlas.operations.collectors import (
    DockerCollectorError,
    DockerCommandRunner,
)


def test_docker_collector_error_is_exception() -> None:
    error = DockerCollectorError("Docker unavailable")

    assert isinstance(error, Exception)
    assert str(error) == "Docker unavailable"


def test_docker_command_runner_can_be_constructed() -> None:
    result = DockerCommandRunner()

    assert isinstance(result, DockerCommandRunner)



def test_docker_command_runner_exposes_expected_methods() -> None:
    runner = DockerCommandRunner()

    assert callable(runner.version)
    assert callable(runner.info)
    assert callable(runner.ps)
    assert callable(runner.inspect)


def test_public_docker_adapter_exports() -> None:
    from atlas.operations import collectors

    assert collectors.DockerCollectorError is DockerCollectorError
    assert collectors.DockerCommandRunner is DockerCommandRunner


def completed(
    *,
    returncode: int = 0,
    stdout: str = '{"ok": true}',
    stderr: str = "",
):
    import subprocess

    return subprocess.CompletedProcess(
        args=["docker"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_run_json_executes_without_shell() -> None:
    calls: list[tuple[object, dict[str, object]]] = []

    def executor(command, **kwargs):
        calls.append((command, kwargs))
        return completed(stdout='{"Server": {"Version": "28.0"}}')

    runner = DockerCommandRunner(
        timeout_seconds=7,
        executor=executor,
    )

    result = runner._run_json(
        "version",
        "--format",
        "{{json .}}",
    )

    assert result == {
        "Server": {
            "Version": "28.0",
        }
    }

    assert calls == [
        (
            [
                "docker",
                "version",
                "--format",
                "{{json .}}",
            ],
            {
                "capture_output": True,
                "text": True,
                "timeout": 7.0,
                "check": False,
            },
        )
    ]


def test_run_json_preserves_array_payload() -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(
            stdout='[{"Names": "atlas-api"}]',
        ),
    )

    assert runner._run_json("ps") == [
        {
            "Names": "atlas-api",
        }
    ]


def test_run_json_rejects_missing_docker_binary() -> None:
    def executor(command, **kwargs):
        raise FileNotFoundError("docker")

    runner = DockerCommandRunner(executor=executor)

    with pytest.raises(
        DockerCollectorError,
        match="Docker CLI is not installed",
    ):
        runner._run_json("info")


def test_run_json_normalizes_timeout() -> None:
    import subprocess

    def executor(command, **kwargs):
        raise subprocess.TimeoutExpired(
            command,
            timeout=3,
        )

    runner = DockerCommandRunner(
        timeout_seconds=3,
        executor=executor,
    )

    with pytest.raises(
        DockerCollectorError,
        match="timed out after 3 seconds",
    ):
        runner._run_json("info")


def test_run_json_rejects_nonzero_exit() -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(
            returncode=1,
            stdout="",
            stderr="Cannot connect to the Docker daemon",
        ),
    )

    with pytest.raises(
        DockerCollectorError,
        match=(
            "exit code 1: "
            "Cannot connect to the Docker daemon"
        ),
    ):
        runner._run_json("info")


def test_run_json_rejects_empty_output() -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(
            stdout="   ",
        ),
    )

    with pytest.raises(
        DockerCollectorError,
        match="returned empty output",
    ):
        runner._run_json("info")


def test_run_json_rejects_invalid_json() -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(
            stdout="not-json",
        ),
    )

    with pytest.raises(
        DockerCollectorError,
        match="returned invalid JSON",
    ):
        runner._run_json("info")


def test_run_json_rejects_invalid_executor_result() -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: object(),
    )

    with pytest.raises(
        DockerCollectorError,
        match="executor returned an invalid result",
    ):
        runner._run_json("info")


@pytest.mark.parametrize(
    "timeout",
    (
        0,
        -1,
        True,
        "10",
        float("inf"),
        float("-inf"),
        float("nan"),
    ),
)
def test_docker_runner_rejects_invalid_timeout(
    timeout: object,
) -> None:
    with pytest.raises(DockerCollectorError):
        DockerCommandRunner(
            timeout_seconds=timeout,  # type: ignore[arg-type]
        )


def test_docker_runner_rejects_non_callable_executor() -> None:
    with pytest.raises(
        DockerCollectorError,
        match="executor must be callable",
    ):
        DockerCommandRunner(
            executor=None,  # type: ignore[arg-type]
        )


def test_version_executes_expected_command() -> None:
    calls: list[list[str]] = []

    def executor(command, **kwargs):
        calls.append(command)
        return completed(
            stdout=(
                '{"Client":{"Version":"28.0"},'
                '"Server":{"Version":"28.0"}}'
            ),
        )

    result = DockerCommandRunner(
        executor=executor,
    ).version()

    assert result["Server"]["Version"] == "28.0"
    assert calls == [
        [
            "docker",
            "version",
            "--format",
            "{{json .}}",
        ]
    ]


def test_info_executes_expected_command() -> None:
    calls: list[list[str]] = []

    def executor(command, **kwargs):
        calls.append(command)
        return completed(
            stdout='{"Containers":30,"ContainersRunning":30}',
        )

    result = DockerCommandRunner(
        executor=executor,
    ).info()

    assert result == {
        "Containers": 30,
        "ContainersRunning": 30,
    }
    assert calls == [
        [
            "docker",
            "info",
            "--format",
            "{{json .}}",
        ]
    ]


def test_ps_parses_newline_delimited_json() -> None:
    calls: list[list[str]] = []

    def executor(command, **kwargs):
        calls.append(command)
        return completed(
            stdout=(
                '{"Names":"atlas-api","State":"running"}\n'
                '{"Names":"jellyfin","State":"running"}\n'
            ),
        )

    result = DockerCommandRunner(
        executor=executor,
    ).ps()

    assert result == [
        {
            "Names": "atlas-api",
            "State": "running",
        },
        {
            "Names": "jellyfin",
            "State": "running",
        },
    ]

    assert calls == [
        [
            "docker",
            "ps",
            "-a",
            "--no-trunc",
            "--format",
            "{{json .}}",
        ]
    ]


def test_ps_returns_empty_list_for_no_containers() -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(
            stdout="",
        ),
    )

    assert runner.ps() == []


def test_inspect_executes_expected_command() -> None:
    calls: list[list[str]] = []

    def executor(command, **kwargs):
        calls.append(command)
        return completed(
            stdout=(
                '{"Name":"/atlas-api",'
                '"State":{"Status":"running"}}'
            ),
        )

    result = DockerCommandRunner(
        executor=executor,
    ).inspect(" atlas-api ")

    assert result["Name"] == "/atlas-api"
    assert calls == [
        [
            "docker",
            "inspect",
            "--format",
            "{{json .}}",
            "atlas-api",
        ]
    ]


@pytest.mark.parametrize(
    ("method_name", "payload", "message"),
    (
        (
            "version",
            "[]",
            "version output must be an object",
        ),
        (
            "info",
            "[]",
            "info output must be an object",
        ),
    ),
)
def test_object_methods_reject_wrong_json_shape(
    method_name: str,
    payload: str,
    message: str,
) -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(
            stdout=payload,
        ),
    )

    method = getattr(runner, method_name)

    with pytest.raises(
        DockerCollectorError,
        match=message,
    ):
        method()


def test_inspect_rejects_wrong_json_shape() -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(
            stdout="[]",
        ),
    )

    with pytest.raises(
        DockerCollectorError,
        match="inspect output must be an object",
    ):
        runner.inspect("atlas-api")


@pytest.mark.parametrize(
    "identity",
    (
        "",
        " ",
        "../atlas-api",
        "atlas/api",
        "atlas api",
        "--help",
        None,
    ),
)
def test_inspect_rejects_invalid_container_identity(
    identity: object,
) -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(),
    )

    with pytest.raises(DockerCollectorError):
        runner.inspect(identity)  # type: ignore[arg-type]


def test_ps_rejects_invalid_json_line() -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(
            stdout=(
                '{"Names":"atlas-api"}\n'
                'not-json\n'
            ),
        ),
    )

    with pytest.raises(
        DockerCollectorError,
        match="invalid JSON on line 2",
    ):
        runner.ps()


def test_ps_rejects_non_object_json_line() -> None:
    runner = DockerCommandRunner(
        executor=lambda command, **kwargs: completed(
            stdout='{"Names":"atlas-api"}\n[]\n',
        ),
    )

    with pytest.raises(
        DockerCollectorError,
        match="line 2 was list",
    ):
        runner.ps()
