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
    # Standalone authority requires explicit, fixture-owned state and exclusion.
    (tmp_path / "maintenance").mkdir(mode=0o700, exist_ok=True)
    (tmp_path / "deployments").mkdir(mode=0o700, exist_ok=True)
    lock = tmp_path / "deployment-scheduler.lock"
    if not lock.exists():
        lock.touch(mode=0o600)
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


def test_caddy_maintenance_precedes_protected_public_upstreams() -> None:
    content = CADDY.read_text(encoding="utf-8")
    liveness = content.index("handle /_atlas/ingress-health")
    static_assets = content.index("handle /maintenance/*")
    auth = content.index("handle @atlas_auth_entry")
    maintenance = content.index("handle @atlas_maintenance")
    guard = content.index("import atlas_required_admin_auth", maintenance)
    api = content.index("reverse_proxy atlas-api:8000", maintenance)
    portal = content.index("reverse_proxy atlas-portal:3000", maintenance)
    assert liveness < static_assets < auth < maintenance < guard < api < portal
    assert "try_files /enabled /control-pending" in content
    assert "method POST" in content
    assert "handle /_atlas/maintenance/*" in content
    assert "import atlas_maintenance_auth" in content
    page = (CADDY.parents[1] / "snippets/maintenance-00-page.caddy").read_text()
    assert 'header Retry-After "300"' in page
    assert "HTML 503" in page


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


def test_caddy_maintenance_page_uses_responsive_tracked_artwork() -> None:
    content = (CADDY.parents[1] / "snippets/maintenance-00-page.caddy").read_text(encoding="utf-8")

    assert "/maintenance/Maintenance_Desktop_Image.png" in content
    assert "/maintenance/Maintenance_Tablet_Image.png" in content
    assert "/maintenance/Maintenance_Phone_Image.png" in content
    assert 'media="(max-width: 640px) and (orientation: portrait)"' in content
    assert 'media="(max-width: 1024px)"' in content
    assert '<h1 id="maintenance-title">' in content
    assert "Project Atlas is currently under maintenance." in content
    assert "We are working to get it back up and running as soon as possible." in content


def test_caddy_maintenance_artwork_files_exist() -> None:
    site = PROJECT_ROOT / "infra" / "caddy" / "site" / "maintenance"

    assert (site / "Maintenance_Desktop_Image.png").is_file()
    assert (site / "Maintenance_Tablet_Image.png").is_file()
    assert (site / "Maintenance_Phone_Image.png").is_file()
