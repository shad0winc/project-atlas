from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import textwrap


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = PROJECT_ROOT / "scripts/commands/deployment.sh"
HELPER = "atlas_deployment_notifications_live_worker_row"
IMAGE_ID = "sha256:" + "a" * 64


def git(checkout: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def setup_case(tmp_path: Path) -> tuple[Path, str, Path]:
    checkout = tmp_path / "historical-checkout"
    checkout.mkdir()
    git(checkout, "init", "-q")
    git(checkout, "config", "user.name", "Atlas Test")
    git(checkout, "config", "user.email", "atlas-test@example.invalid")

    worker = checkout / "modules/notifications/scripts/worker.sh"
    worker.parent.mkdir(parents=True)
    worker.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")

    git(checkout, "add", ".")
    git(checkout, "commit", "-qm", "Historical worker fixture")
    commit = git(checkout, "rev-parse", "HEAD")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            [[ "$#" -eq 2 && "$1" == inspect &&
               "$2" == atlas-notifications-worker ]] || exit 96
            cat -- "$ATLAS_TEST_DOCKER_INSPECT"
            """
        ),
        encoding="utf-8",
    )
    docker.chmod(0o755)
    return checkout, commit, bin_dir


def container_details(checkout: Path) -> dict:
    return {
        "Name": "/atlas-notifications-worker",
        "Image": IMAGE_ID,
        "State": {
            "Status": "running",
            "Health": {"Status": "healthy"},
        },
        "Config": {
            "Image": "notifications-atlas-notifications-worker:local",
            "Labels": {
                "com.docker.compose.project": "notifications",
                "com.docker.compose.service": "atlas-notifications-worker",
            },
        },
        "Mounts": [{
            "Type": "bind",
            "Source": str(checkout.resolve()),
            "Destination": "/opt/project-atlas",
            "RW": False,
        }],
    }


def attest(
    checkout: Path,
    commit: str,
    bin_dir: Path,
    details: dict,
) -> subprocess.CompletedProcess[str]:
    inspection = bin_dir.parent / "inspect.json"
    inspection.write_text(
        json.dumps([details]), encoding="utf-8"
    )

    environment = {
        **os.environ,
        "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        "ATLAS_TEST_HELPER": HELPER,
        "ATLAS_TEST_DOCKER_INSPECT": str(inspection),
    }

    return subprocess.run(
        [
            "bash", "-c",
            'set -euo pipefail; '
            'source "$ATLAS_TEST_DEPLOYMENT"; '
            '"$ATLAS_TEST_HELPER" "$1" "$2"',
            "attestation-test", str(checkout), commit,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def test_attests_exact_healthy_worker_image_and_source(
    tmp_path: Path,
) -> None:
    checkout, commit, bin_dir = setup_case(tmp_path)
    details = container_details(checkout)

    result = attest(checkout, commit, bin_dir, details)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "|".join([
        "notifications",
        "modules/notifications/docker-compose.yml",
        "notifications",
        "atlas-notifications-worker",
        "/atlas-notifications-worker",
        "notifications-atlas-notifications-worker:local",
        IMAGE_ID,
    ])


def test_rejects_worker_mounted_from_another_checkout(
    tmp_path: Path,
) -> None:
    checkout, commit, bin_dir = setup_case(tmp_path)
    details = container_details(checkout)
    details["Mounts"][0]["Source"] = str(tmp_path / "other-checkout")

    result = attest(checkout, commit, bin_dir, details)

    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_rejects_worker_with_writable_application_mount(
    tmp_path: Path,
) -> None:
    checkout, commit, bin_dir = setup_case(tmp_path)
    details = container_details(checkout)
    details["Mounts"][0]["RW"] = True

    result = attest(checkout, commit, bin_dir, details)

    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_rejects_unhealthy_worker(
    tmp_path: Path,
) -> None:
    checkout, commit, bin_dir = setup_case(tmp_path)
    details = container_details(checkout)
    details["State"]["Health"]["Status"] = "unhealthy"

    result = attest(checkout, commit, bin_dir, details)

    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_rejects_unexpected_compose_identity(
    tmp_path: Path,
) -> None:
    checkout, commit, bin_dir = setup_case(tmp_path)
    details = container_details(checkout)
    details["Config"]["Labels"]["com.docker.compose.project"] = "other"

    result = attest(checkout, commit, bin_dir, details)

    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_rejects_checkout_commit_mismatch(
    tmp_path: Path,
) -> None:
    checkout, commit, bin_dir = setup_case(tmp_path)
    details = container_details(checkout)

    result = attest(checkout, "0" * 40, bin_dir, details)

    assert result.returncode != 0
    assert result.stdout.strip() == ""
