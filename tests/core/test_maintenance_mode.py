from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMAND = PROJECT_ROOT / "scripts" / "commands" / "maintenance.sh"
ATLAS = PROJECT_ROOT / "scripts" / "atlas"
HELP = PROJECT_ROOT / "scripts" / "commands" / "help.sh"
CADDY = PROJECT_ROOT / "infra" / "caddy" / "sites" / "atlas.caddy"
INGRESS = PROJECT_ROOT / "stack" / "ingress.yml"


def run_maintenance(tmp_path: Path, action: str) -> subprocess.CompletedProcess[str]:
    script = textwrap.dedent(
        f"""
        set -euo pipefail
        ATLAS_RUNTIME_CONFIG_DIR={tmp_path!s}
        source {COMMAND!s}
        atlas_command_maintenance {action}
        """
    )
    environment = os.environ.copy()
    environment.pop("ATLAS_MAINTENANCE_DIR", None)
    return subprocess.run(
        ["bash", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_maintenance_status_defaults_disabled(tmp_path: Path) -> None:
    result = run_maintenance(tmp_path, "status")

    assert result.returncode == 0
    assert result.stdout.strip() == "Atlas maintenance mode: disabled"


def test_maintenance_enable_persists_runtime_flag(tmp_path: Path) -> None:
    result = run_maintenance(tmp_path, "enable")

    assert result.returncode == 0
    assert (tmp_path / "maintenance" / "enabled").is_file()

    status = run_maintenance(tmp_path, "status")
    assert status.stdout.strip() == "Atlas maintenance mode: enabled"


def test_maintenance_disable_removes_runtime_flag(tmp_path: Path) -> None:
    assert run_maintenance(tmp_path, "enable").returncode == 0

    result = run_maintenance(tmp_path, "disable")

    assert result.returncode == 0
    assert not (tmp_path / "maintenance" / "enabled").exists()


def test_maintenance_unknown_action_fails_closed(tmp_path: Path) -> None:
    result = run_maintenance(tmp_path, "surprise")

    assert result.returncode == 2
    assert "Unknown maintenance action" in result.stderr


def test_atlas_dispatches_maintenance_command() -> None:
    content = ATLAS.read_text(encoding="utf-8")

    assert 'source "$ATLAS_CLI_ROOT/commands/maintenance.sh"' in content
    assert "atlas_command_maintenance \"${@:2}\"" in content


def test_help_exposes_maintenance_commands() -> None:
    content = HELP.read_text(encoding="utf-8")

    assert "atlas maintenance status" in content
    assert "atlas maintenance enable" in content
    assert "atlas maintenance disable" in content


def test_caddy_maintenance_precedes_public_upstreams() -> None:
    content = CADDY.read_text(encoding="utf-8")

    liveness = content.index("handle /_atlas/ingress-health")
    maintenance = content.index("handle @atlas_maintenance")
    api = content.index("reverse_proxy atlas-api:8000")
    portal = content.index("reverse_proxy atlas-portal:3000")

    assert liveness < maintenance < api < portal
    assert "try_files /enabled" in content
    assert 'header Retry-After "300"' in content
    assert "503" in content


def test_ingress_health_bypasses_upstream_health() -> None:
    content = INGRESS.read_text(encoding="utf-8")

    assert "https://atlas.shadowinc.co/_atlas/ingress-health" in content
    assert "https://atlas.shadowinc.co/api/v1/health" not in content


def test_ingress_mounts_runtime_maintenance_state_read_only() -> None:
    content = INGRESS.read_text(encoding="utf-8")

    assert (
        "/mnt/storage/configs/atlas/maintenance:/etc/atlas-maintenance:ro"
        in content
    )
