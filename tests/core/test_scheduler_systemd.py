"""Systemd contract tests for the Atlas Scheduler dispatcher."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_ROOT = PROJECT_ROOT / "systemd"

SERVICE = SYSTEMD_ROOT / "atlas-scheduler.service"
TIMER = SYSTEMD_ROOT / "atlas-scheduler.timer"

HEALTH_SERVICE = SYSTEMD_ROOT / "atlas-health-report.service"
HEALTH_TIMER = SYSTEMD_ROOT / "atlas-health-report.timer"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_scheduler_service_exists() -> None:
    assert SERVICE.is_file()


def test_scheduler_timer_exists() -> None:
    assert TIMER.is_file()


def test_scheduler_service_is_oneshot() -> None:
    text = _text(SERVICE)

    assert "[Service]" in text
    assert "Type=oneshot" in text


def test_scheduler_service_uses_canonical_project_directory() -> None:
    assert (
        "WorkingDirectory=/opt/project-atlas"
        in _text(SERVICE)
    )


def test_scheduler_service_uses_public_atlas_cli() -> None:
    text = _text(SERVICE)

    assert (
        "ExecStart=/bin/atlas scheduler run"
        in text
    )

    assert "python " not in text
    assert "python3 " not in text
    assert "scheduler_cli.py" not in text


def test_scheduler_service_waits_for_docker() -> None:
    text = _text(SERVICE)

    assert "After=docker.service" in text
    assert "Wants=docker.service" in text


def test_scheduler_service_does_not_create_second_runtime() -> None:
    text = _text(SERVICE).lower()

    forbidden = (
        "restart=always",
        "restart=on-failure",
        "watchdog",
        "daemon",
        "while true",
        "sleep ",
    )

    for marker in forbidden:
        assert marker not in text


def test_scheduler_timer_targets_dispatcher_service() -> None:
    assert (
        "Unit=atlas-scheduler.service"
        in _text(TIMER)
    )


def test_scheduler_timer_uses_one_minute_dispatch_opportunity() -> None:
    text = _text(TIMER)

    assert "OnBootSec=1min" in text
    assert "OnUnitActiveSec=1min" in text


def test_scheduler_timer_is_persistent() -> None:
    assert "Persistent=true" in _text(TIMER)


def test_scheduler_timer_is_installable() -> None:
    text = _text(TIMER)

    assert "[Install]" in text
    assert "WantedBy=timers.target" in text


def test_scheduler_timer_does_not_encode_task_intervals() -> None:
    text = _text(TIMER)

    assert "15min" not in text
    assert "900" not in text
    assert "1h" not in text
    assert "3600" not in text


def test_scheduler_dispatcher_does_not_replace_existing_health_timer() -> None:
    assert HEALTH_SERVICE.is_file()
    assert HEALTH_TIMER.is_file()

    scheduler_service = _text(SERVICE)
    scheduler_timer = _text(TIMER)

    assert "atlas-health-report" not in scheduler_service
    assert "atlas-health-report" not in scheduler_timer


def test_existing_health_report_systemd_contract_remains_separate() -> None:
    health_service = _text(HEALTH_SERVICE)
    health_timer = _text(HEALTH_TIMER)

    assert "Type=oneshot" in health_service
    assert (
        "ExecStart=/bin/atlas ari collect"
        in health_service
    )
    assert (
        "ExecStart=/bin/atlas ari health-report"
        in health_service
    )
    assert "Persistent=true" in health_timer


def test_dispatcher_has_no_scheduler_state_path() -> None:
    combined = (
        _text(SERVICE)
        + "\n"
        + _text(TIMER)
    )

    assert "tasks.json" not in combined
    assert "tasks.lock" not in combined


def test_dispatcher_has_no_q6_specific_ownership() -> None:
    combined = (
        _text(SERVICE)
        + "\n"
        + _text(TIMER)
    ).lower()

    assert "sustained-use" not in combined
    assert "q.6" not in combined
    assert "q6" not in combined


def test_dispatcher_has_no_module_specific_ownership() -> None:
    combined = (
        _text(SERVICE)
        + "\n"
        + _text(TIMER)
    ).lower()

    assert "sports" not in combined
    assert "operations.collect" not in combined


def test_service_and_timer_end_with_newline() -> None:
    assert SERVICE.read_bytes().endswith(b"\n")
    assert TIMER.read_bytes().endswith(b"\n")


# ---------------------------------------------------------------------------
# Dispatcher process exit semantics
# ---------------------------------------------------------------------------


def _isolated_cli(
    tmp_path,
    monkeypatch,
):
    """Return an isolated scheduler plus the production CLI adapter."""

    import atlas.scheduler_cli as scheduler_cli

    from atlas.scheduler import TaskScheduler

    state_file = tmp_path / "tasks.json"
    lock_file = tmp_path / "tasks.lock"

    scheduler = TaskScheduler(
        state_file,
        lock_file=lock_file,
        working_directory=PROJECT_ROOT,
    )

    monkeypatch.setattr(
        scheduler_cli,
        "scheduler_state_file",
        lambda: state_file,
    )

    monkeypatch.setattr(
        scheduler_cli,
        "scheduler_lock_file",
        lambda: lock_file,
    )

    monkeypatch.setattr(
        scheduler_cli,
        "_publish_scheduler_event",
        lambda *args, **kwargs: None,
    )

    return scheduler_cli, scheduler, state_file, lock_file


def test_dispatcher_exit_zero_when_no_tasks_are_due(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    scheduler_cli, _, _, _ = _isolated_cli(
        tmp_path,
        monkeypatch,
    )

    result = scheduler_cli.main(["run"])

    assert result == 0
    assert capsys.readouterr().out.strip() == "[]"


def test_dispatcher_exit_zero_when_due_callback_succeeds(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    scheduler_cli, scheduler, _, _ = _isolated_cli(
        tmp_path,
        monkeypatch,
    )

    scheduler.register(
        "probe.success",
        60,
        "/bin/true",
    )

    result = scheduler_cli.main(["run"])

    assert result == 0

    capsys.readouterr()

    state = scheduler.task_state(
        "probe.success"
    )

    assert state is not None
    assert state["status"] == "healthy"
    assert state["run_count"] == 1
    assert state["failure_count"] == 0
    assert state["consecutive_failures"] == 0
    assert state["last_success"] is not None


def test_dispatcher_exit_one_when_due_callback_fails(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    scheduler_cli, scheduler, _, _ = _isolated_cli(
        tmp_path,
        monkeypatch,
    )

    scheduler.register(
        "probe.failure",
        60,
        "/bin/false",
    )

    result = scheduler_cli.main(["run"])

    assert result == 1

    capsys.readouterr()

    state = scheduler.task_state(
        "probe.failure"
    )

    assert state is not None
    assert state["status"] == "degraded"
    assert state["run_count"] == 1
    assert state["failure_count"] == 1
    assert state["consecutive_failures"] == 1
    assert state.get("last_success") is None


def test_dispatcher_attempts_all_due_tasks_and_returns_failure(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    scheduler_cli, scheduler, _, _ = _isolated_cli(
        tmp_path,
        monkeypatch,
    )

    scheduler.register(
        "probe.failure",
        60,
        "/bin/false",
    )

    scheduler.register(
        "probe.success",
        60,
        "/bin/true",
    )

    result = scheduler_cli.main(["run"])

    assert result == 1

    capsys.readouterr()

    failed = scheduler.task_state(
        "probe.failure"
    )

    succeeded = scheduler.task_state(
        "probe.success"
    )

    assert failed is not None
    assert succeeded is not None

    assert failed["run_count"] == 1
    assert failed["failure_count"] == 1
    assert failed["status"] == "degraded"

    assert succeeded["run_count"] == 1
    assert succeeded["failure_count"] == 0
    assert succeeded["status"] == "healthy"


def test_dispatcher_exit_three_when_runtime_lock_is_owned(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    import os

    scheduler_cli, scheduler, _, lock_file = _isolated_cli(
        tmp_path,
        monkeypatch,
    )

    scheduler.register(
        "probe.locked",
        60,
        "/bin/true",
    )

    lock_file.write_text(
        f"{os.getpid()}\n",
        encoding="utf-8",
    )

    result = scheduler_cli.main(["run"])

    assert result == 3

    output = capsys.readouterr().out

    assert "Scheduler error:" in output

    state = scheduler.task_state(
        "probe.locked"
    )

    assert state is not None
    assert state["run_count"] == 0
    assert state["failure_count"] == 0
    assert state["status"] == "never_run"


def test_dispatcher_locked_execution_preserves_live_lock_file(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    import os

    scheduler_cli, scheduler, _, lock_file = _isolated_cli(
        tmp_path,
        monkeypatch,
    )

    scheduler.register(
        "probe.locked",
        60,
        "/bin/true",
    )

    lock_file.write_text(
        f"{os.getpid()}\n",
        encoding="utf-8",
    )

    assert scheduler_cli.main(["run"]) == 3

    capsys.readouterr()

    assert lock_file.is_file()
    assert lock_file.read_text(
        encoding="utf-8"
    ) == f"{os.getpid()}\n"


def test_systemd_service_propagates_scheduler_cli_exit_status() -> None:
    text = _text(SERVICE)

    exec_lines = [
        line
        for line in text.splitlines()
        if line.startswith("ExecStart=")
    ]

    assert exec_lines == [
        "ExecStart=/bin/atlas scheduler run",
    ]

    assert "SuccessExitStatus=" not in text
    assert "ExecStart=-" not in text


def test_systemd_service_does_not_mask_dispatch_failures() -> None:
    text = _text(SERVICE)

    forbidden = (
        "|| true",
        "ignore_errors",
        "SuccessExitStatus=1",
        "SuccessExitStatus=3",
    )

    for marker in forbidden:
        assert marker not in text


def test_scheduler_event_publisher_uses_core_event_contract(
    monkeypatch,
) -> None:
    import atlas.scheduler_cli as scheduler_cli

    published = []

    def fake_publish_core_event(
        event_name,
        payload,
        *,
        source="atlas",
        atlas_binary=None,
    ):
        published.append(
            {
                "event_name": event_name,
                "payload": payload,
                "source": source,
                "atlas_binary": atlas_binary,
            }
        )

    monkeypatch.setattr(
        scheduler_cli,
        "publish_core_event",
        fake_publish_core_event,
    )

    payload = {
        "task": "sports.maintenance",
        "module": "sports",
        "return_code": 0,
    }

    scheduler_cli._publish_scheduler_event(
        "scheduler.task.completed",
        payload,
    )

    assert published == [
        {
            "event_name": "scheduler.task.completed",
            "payload": payload,
            "source": "scheduler",
            "atlas_binary": None,
        }
    ]


def test_scheduler_event_publisher_core_route_ignores_module_ownership(
    monkeypatch,
) -> None:
    import atlas.scheduler_cli as scheduler_cli

    published = []

    def fake_publish_core_event(
        event_name,
        payload,
        *,
        source="atlas",
        atlas_binary=None,
    ):
        published.append(
            (
                event_name,
                payload,
                source,
            )
        )

    monkeypatch.setattr(
        scheduler_cli,
        "publish_core_event",
        fake_publish_core_event,
    )

    scheduler_cli._publish_scheduler_event(
        "scheduler.task.started",
        {
            "task": "sports.maintenance",
            "module": "sports",
        },
    )

    assert published == [
        (
            "scheduler.task.started",
            {
                "task": "sports.maintenance",
                "module": "sports",
            },
            "scheduler",
        )
    ]


def test_scheduler_event_publisher_core_route_supports_core_task(
    monkeypatch,
) -> None:
    import atlas.scheduler_cli as scheduler_cli

    published = []

    def fake_publish_core_event(
        event_name,
        payload,
        *,
        source="atlas",
        atlas_binary=None,
    ):
        published.append(
            (
                event_name,
                payload,
                source,
            )
        )

    monkeypatch.setattr(
        scheduler_cli,
        "publish_core_event",
        fake_publish_core_event,
    )

    scheduler_cli._publish_scheduler_event(
        "scheduler.task.completed",
        {
            "task": "operations.collect",
            "module": None,
            "return_code": 0,
        },
    )

    assert published == [
        (
            "scheduler.task.completed",
            {
                "task": "operations.collect",
                "module": None,
                "return_code": 0,
            },
            "scheduler",
        )
    ]
