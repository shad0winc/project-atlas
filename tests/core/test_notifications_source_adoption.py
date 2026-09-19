from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tarfile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = PROJECT_ROOT / "scripts/commands/deployment.sh"

HELPER = "atlas_deployment_archive_notifications_checkout"


def git(checkout: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def make_checkout(tmp_path: Path) -> tuple[Path, str]:
    checkout = tmp_path / "live-checkout"
    checkout.mkdir()
    git(checkout, "init", "-q")
    git(checkout, "config", "user.name", "Atlas Test")
    git(checkout, "config", "user.email", "atlas-test@example.invalid")

    (checkout / ".gitignore").write_text(
        "ignored-runtime/\n", encoding="utf-8"
    )

    source = checkout / "modules/notifications/src"
    source.mkdir(parents=True)
    (source / "formatter.py").write_text(
        "HISTORICAL_MARKER = 'live-revision'\n",
        encoding="utf-8",
    )

    git(checkout, "add", ".gitignore", "modules/notifications/src/formatter.py")
    git(checkout, "commit", "-qm", "Historical Notifications fixture")

    ignored = checkout / "ignored-runtime"
    ignored.mkdir()
    (ignored / "not-for-archive.txt").write_text(
        "runtime-only\n", encoding="utf-8"
    )

    return checkout, git(checkout, "rev-parse", "HEAD")


def archive(
    checkout: Path,
    commit: str,
    output: Path,
) -> subprocess.CompletedProcess[str]:
    script = (
        'set -euo pipefail; '
        'source "$ATLAS_TEST_DEPLOYMENT"; '
        '"$ATLAS_TEST_HELPER" "$1" "$2" "$3"'
    )

    environment = {
        **os.environ,
        "ATLAS_TEST_DEPLOYMENT": str(DEPLOYMENT),
        "ATLAS_TEST_HELPER": HELPER,
    }

    return subprocess.run(
        [
            "bash", "-c", script, "archive-test",
            str(checkout), commit, str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def test_archives_exact_live_checkout_commit_without_ignored_files(
    tmp_path: Path,
) -> None:
    checkout, commit = make_checkout(tmp_path)
    output = tmp_path / "historical-notifications.tar.gz"

    result = archive(checkout, commit, output)

    assert result.returncode == 0, result.stderr
    assert output.is_file()

    with tarfile.open(output, "r:gz") as contents:
        names = set(contents.getnames())
        member = contents.extractfile(
            "modules/notifications/src/formatter.py"
        )
        assert member is not None
        assert member.read() == b"HISTORICAL_MARKER = 'live-revision'\n"

    assert "ignored-runtime/not-for-archive.txt" not in names


def test_rejects_checkout_with_uncommitted_tracked_changes(
    tmp_path: Path,
) -> None:
    checkout, commit = make_checkout(tmp_path)
    output = tmp_path / "should-not-exist.tar.gz"

    formatter = checkout / "modules/notifications/src/formatter.py"
    formatter.write_text("HISTORICAL_MARKER = 'changed'\n", encoding="utf-8")

    result = archive(checkout, commit, output)

    assert result.returncode != 0
    assert not output.exists()


def test_rejects_checkout_with_untracked_files(
    tmp_path: Path,
) -> None:
    checkout, commit = make_checkout(tmp_path)
    output = tmp_path / "should-not-exist.tar.gz"

    (checkout / "untracked.py").write_text(
        "untracked = True\n", encoding="utf-8"
    )

    result = archive(checkout, commit, output)

    assert result.returncode != 0
    assert not output.exists()


def test_rejects_commit_that_is_not_live_checkout_head(
    tmp_path: Path,
) -> None:
    checkout, commit = make_checkout(tmp_path)
    output = tmp_path / "should-not-exist.tar.gz"

    different_commit = "0" * 40
    assert different_commit != commit

    result = archive(checkout, different_commit, output)

    assert result.returncode != 0
    assert not output.exists()


def test_rejects_existing_archive_destination(
    tmp_path: Path,
) -> None:
    checkout, commit = make_checkout(tmp_path)
    output = tmp_path / "existing.tar.gz"
    output.write_bytes(b"existing-preserved")

    result = archive(checkout, commit, output)

    assert result.returncode != 0
    assert output.read_bytes() == b"existing-preserved"
