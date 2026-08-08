from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERIFY_INGRESS = PROJECT_ROOT / "scripts" / "verify-ingress.sh"


def _write_fake_docker(path: Path) -> None:
    path.write_text(
        textwrap.dedent(
            r"""
            #!/usr/bin/env bash
            set -euo pipefail

            if [[ "${1:-}" == "compose" || "${1:-} ${2:-}" == "network inspect" ]]; then
              exit 0
            fi

            if [[ "${1:-}" == "inspect" ]]; then
              container="$2"
              template="${4:-}"
              case "$template" in
                '{{.State.Status}}') echo running ;;
                '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}') echo healthy ;;
                '{{.HostConfig.Memory}}')
                  case "$container" in
                    atlas-caddy) echo 536870912 ;;
                    atlas-api) echo 1073741824 ;;
                    atlas-portal) echo 1610612736 ;;
                  esac ;;
                '{{.HostConfig.NanoCpus}}')
                  case "$container" in
                    atlas-caddy) echo 1000000000 ;;
                    atlas-api|atlas-portal) echo 2000000000 ;;
                  esac ;;
                '{{.HostConfig.PidsLimit}}')
                  case "$container" in
                    atlas-caddy) echo 256 ;;
                    atlas-api|atlas-portal) echo 512 ;;
                  esac ;;
                *) exit 0 ;;
              esac
              exit 0
            fi

            if [[ "${1:-} ${2:-} ${3:-}" == "exec atlas-caddy caddy" ]]; then
              exit 0
            fi

            if [[ "${1:-} ${2:-} ${3:-}" == "exec atlas-caddy curl" ]]; then
              args=" $* "
              if [[ "$args" == *" http://atlas-api:8000/api/v1/health "* ]]; then
                printf '%s\n' '{"status":"ok"}'
                exit 0
              fi
              if [[ "$args" == *" http://atlas-portal:3000/ "* ]]; then
                exit 0
              fi
              if [[ "$args" == *" /_atlas/ingress-health "* ]]; then
                exit 0
              fi
              if [[ "$args" == *" --write-out %{http_code} "* ]]; then
                printf '%s' "${ATLAS_TEST_PUBLIC_STATUS:-503}"
                exit 0
              fi
              if [[ "$args" == *"/api/v1/health "* ]]; then
                printf '%s\n' '{"status":"ok"}'
                exit 0
              fi
              exit 0
            fi

            exit 1
            """
        ).lstrip(),
        encoding="utf-8",
    )
    path.chmod(0o755)


def _run_verifier(tmp_path: Path, *, maintenance: bool, public_status: str = "503") -> subprocess.CompletedProcess[str]:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    bin_dir = tmp_path / "bin"
    (project / "stack").mkdir(parents=True)
    runtime.mkdir()
    bin_dir.mkdir()
    (project / "stack" / "ingress.yml").write_text("services: {}\n", encoding="utf-8")
    if maintenance:
        maintenance_dir = runtime / "maintenance"
        maintenance_dir.mkdir()
        (maintenance_dir / "enabled").touch()
    _write_fake_docker(bin_dir / "docker")
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{bin_dir}:{environment['PATH']}",
            "ATLAS_PROJECT_DIR": str(project),
            "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
            "ATLAS_TEST_PUBLIC_STATUS": public_status,
        }
    )
    return subprocess.run(
        ["bash", str(VERIFY_INGRESS)],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_normal_mode_requires_public_routes(tmp_path: Path) -> None:
    result = _run_verifier(tmp_path, maintenance=False)

    assert result.returncode == 0, result.stderr
    assert "Portal route reachable through Caddy" in result.stdout
    assert "API route reachable through Caddy" in result.stdout
    assert "Atlas Ingress Status: PASS" in result.stdout


def test_maintenance_mode_proves_backends_and_public_isolation(tmp_path: Path) -> None:
    result = _run_verifier(tmp_path, maintenance=True)

    assert result.returncode == 0, result.stderr
    assert "Caddy maintenance liveness reachable" in result.stdout
    assert "Portal backend reachable during maintenance" in result.stdout
    assert "API backend reachable during maintenance" in result.stdout
    assert "Portal public maintenance isolation" in result.stdout
    assert "API public maintenance isolation" in result.stdout
    assert "Atlas Ingress Status: PASS" in result.stdout


def test_maintenance_mode_fails_if_public_traffic_is_not_isolated(tmp_path: Path) -> None:
    result = _run_verifier(tmp_path, maintenance=True, public_status="200")

    assert result.returncode != 0
    assert "Portal public maintenance isolation" in result.stderr
    assert "API public maintenance isolation" in result.stderr
    assert "Atlas Ingress Status: FAIL" in result.stderr
