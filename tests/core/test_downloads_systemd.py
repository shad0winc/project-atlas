from __future__ import annotations

from pathlib import Path
import os
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYSTEMD_ROOT = PROJECT_ROOT / "systemd"

SERVICE = SYSTEMD_ROOT / "atlas-downloads-runtime.service"
TIMER = SYSTEMD_ROOT / "atlas-downloads-runtime.timer"
RUNTIME_SCRIPT = PROJECT_ROOT / "scripts" / "atlas-downloads-runtime.sh"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_downloads_runtime_service_exists() -> None:
    assert SERVICE.is_file()


def test_downloads_runtime_timer_exists() -> None:
    assert TIMER.is_file()


def test_downloads_runtime_service_is_oneshot() -> None:
    assert "Type=oneshot" in _text(SERVICE)


def test_downloads_runtime_service_uses_canonical_project_directory() -> None:
    assert "WorkingDirectory=/opt/project-atlas" in _text(SERVICE)


def test_downloads_runtime_service_uses_public_atlas_cli() -> None:
    text = _text(SERVICE)

    assert "ExecStart=/bin/atlas downloads-runtime publish" in text
    assert "python " not in text
    assert "python3 " not in text


def test_downloads_runtime_service_waits_for_docker() -> None:
    text = _text(SERVICE)

    assert "After=docker.service" in text
    assert "Wants=docker.service" in text


def test_downloads_runtime_units_do_not_embed_credentials() -> None:
    combined = (_text(SERVICE) + "\n" + _text(TIMER)).lower()

    forbidden = (
        "atlas_qbittorrent_username",
        "atlas_qbittorrent_password",
        "password=",
        "username=",
        "environment=",
        "environmentfile=",
    )

    for marker in forbidden:
        assert marker not in combined


def test_downloads_runtime_timer_targets_publisher_service() -> None:
    assert "Unit=atlas-downloads-runtime.service" in _text(TIMER)


def test_downloads_runtime_timer_uses_one_minute_publication_opportunity() -> None:
    text = _text(TIMER)

    assert "OnBootSec=1min" in text
    assert "OnUnitActiveSec=1min" in text


def test_downloads_runtime_timer_is_persistent_and_installable() -> None:
    text = _text(TIMER)

    assert "Persistent=true" in text
    assert "[Install]" in text
    assert "WantedBy=timers.target" in text


def test_downloads_runtime_units_are_independent_of_scheduler() -> None:
    combined = _text(SERVICE) + "\n" + _text(TIMER)

    assert "atlas-scheduler" not in combined
    assert "scheduler run" not in combined


def test_downloads_runtime_units_end_with_newline() -> None:
    assert SERVICE.read_bytes().endswith(b"\n")
    assert TIMER.read_bytes().endswith(b"\n")


def test_example_credentials_fail_closed_before_network_access() -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_QBITTORRENT_USERNAME": "CHANGE_ME",
            "ATLAS_QBITTORRENT_PASSWORD": "CHANGE_ME",
            "ATLAS_QBITTORRENT_BASE_URL": "http://127.0.0.1:1",
        }
    )

    result = subprocess.run(
        [str(RUNTIME_SCRIPT), "publish"],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )

    assert result.returncode == 2
    assert "example placeholder" in result.stderr
    assert "authentication failed" not in result.stderr.lower()
    assert "CHANGE_ME" not in result.stderr
