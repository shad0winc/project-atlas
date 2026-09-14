"""Immutable scheduler runtime-source deployment contract tests."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tarfile
import textwrap


DEPLOYMENT = Path("scripts/commands/deployment.sh")
SYSTEMD = Path("systemd/atlas-scheduler.service")


def _write_source_tree(root: Path) -> None:
    (root / "scripts" / "commands").mkdir(parents=True)
    (root / "atlas").mkdir()

    (root / "VERSION").write_text(
        "1.0.0-rc.1\n",
        encoding="utf-8",
    )

    atlas_cli = root / "scripts" / "atlas"
    atlas_cli.write_text(
        "#!/usr/bin/env bash\nexit 0\n",
        encoding="utf-8",
    )
    atlas_cli.chmod(0o755)

    (root / "scripts" / "commands" / "scheduler.sh").write_text(
        "# scheduler\n",
        encoding="utf-8",
    )
    (root / "atlas" / "scheduler.py").write_text(
        "# scheduler\n",
        encoding="utf-8",
    )
    (root / "atlas" / "scheduler_cli.py").write_text(
        "# scheduler cli\n",
        encoding="utf-8",
    )


def _archive_source(source: Path, destination: Path) -> None:
    with tarfile.open(destination, "w:gz") as archive:
        for path in sorted(source.rglob("*")):
            archive.add(
                path,
                arcname=path.relative_to(source),
                recursive=False,
            )


def _run_harness(
    *,
    project: Path,
    runtime: Path,
    deployment_id: str,
) -> subprocess.CompletedProcess[str]:
    harness = r"""
    set -euo pipefail

    source "$ATLAS_TEST_DEPLOYMENT"

    atlas_deployment_set_current "$ATLAS_TEST_ID"

    printf 'current='
    cat "$(atlas_deployment_current_file)"

    generation="$(
      atlas_deployment_runtime_source_generation_dir \
        "$ATLAS_TEST_ID"
    )"

    printf 'generation=%s\n' "$generation"

    test -d "$generation"
    test ! -L "$generation"
    test -x "$generation/scripts/atlas"
    test -f "$generation/.atlas-source-sha256"
    test -f "$generation/.atlas-deployment-id"
    """

    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_PROJECT_DIR": str(project),
            "ATLAS_RUNTIME_CONFIG_DIR": str(runtime),
            "ATLAS_TEST_DEPLOYMENT": str(
                DEPLOYMENT.resolve()
            ),
            "ATLAS_TEST_ID": deployment_id,
        }
    )

    return subprocess.run(
        [
            "bash",
            "-c",
            textwrap.dedent(harness),
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_set_current_materializes_verified_runtime_source_first(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    source = tmp_path / "source"

    project.mkdir()
    runtime.mkdir()
    source.mkdir()

    _write_source_tree(source)

    env_file = project / ".env"
    env_file.write_text(
        "ATLAS_TEST_VALUE=present\n",
        encoding="utf-8",
    )
    env_file.chmod(0o640)

    deployment_id = "update-test"
    record = (
        runtime
        / "deployments"
        / "records"
        / deployment_id
    )
    record.mkdir(parents=True)

    (record / "status").write_text(
        "verified\n",
        encoding="utf-8",
    )

    _archive_source(
        source,
        record / "core-source.tar.gz",
    )

    result = _run_harness(
        project=project,
        runtime=runtime,
        deployment_id=deployment_id,
    )

    assert result.returncode == 0, result.stderr

    current = (
        runtime
        / "deployments"
        / "current"
    ).read_text(
        encoding="utf-8"
    )

    assert current == deployment_id + "\n"

    generation = (
        runtime
        / "source"
        / "generations"
        / deployment_id
    )

    assert generation.is_dir()
    assert not generation.is_symlink()
    assert (
        generation
        / "scripts"
        / "atlas"
    ).stat().st_mode & 0o111

    env_link = generation / ".env"
    assert env_link.is_symlink()
    assert env_link.resolve() == env_file.resolve()

    assert not (
        generation
        / ".env.example-does-not-matter"
    ).exists()


def test_set_current_refuses_unverified_runtime_source(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    source = tmp_path / "source"

    project.mkdir()
    runtime.mkdir()
    source.mkdir()

    _write_source_tree(source)

    deployment_id = "update-test"
    record = (
        runtime
        / "deployments"
        / "records"
        / deployment_id
    )
    record.mkdir(parents=True)

    (record / "status").write_text(
        "prepared\n",
        encoding="utf-8",
    )

    _archive_source(
        source,
        record / "core-source.tar.gz",
    )

    result = _run_harness(
        project=project,
        runtime=runtime,
        deployment_id=deployment_id,
    )

    assert result.returncode != 0

    assert not (
        runtime
        / "deployments"
        / "current"
    ).exists()

    assert not (
        runtime
        / "source"
        / "generations"
        / deployment_id
    ).exists()


def test_existing_generation_must_match_archive_identity(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    source = tmp_path / "source"

    project.mkdir()
    runtime.mkdir()
    source.mkdir()

    _write_source_tree(source)

    deployment_id = "update-test"
    record = (
        runtime
        / "deployments"
        / "records"
        / deployment_id
    )
    record.mkdir(parents=True)

    (record / "status").write_text(
        "verified\n",
        encoding="utf-8",
    )

    _archive_source(
        source,
        record / "core-source.tar.gz",
    )

    generation = (
        runtime
        / "source"
        / "generations"
        / deployment_id
    )
    generation.mkdir(parents=True)

    (
        generation
        / ".atlas-source-sha256"
    ).write_text(
        "not-the-real-archive-hash\n",
        encoding="utf-8",
    )

    scripts = generation / "scripts"
    scripts.mkdir()

    atlas_cli = scripts / "atlas"
    atlas_cli.write_text(
        "#!/usr/bin/env bash\n",
        encoding="utf-8",
    )
    atlas_cli.chmod(0o755)

    result = _run_harness(
        project=project,
        runtime=runtime,
        deployment_id=deployment_id,
    )

    assert result.returncode != 0

    assert "archive identity differs" in result.stderr

    assert not (
        runtime
        / "deployments"
        / "current"
    ).exists()


def test_scheduler_unit_uses_authoritative_deployment_generation() -> None:
    service = SYSTEMD.read_text(
        encoding="utf-8"
    )

    assert (
        "WorkingDirectory="
        "/mnt/storage/configs/atlas/source"
        in service
    )

    assert (
        "/mnt/storage/configs/atlas/deployments/current"
        in service
    )

    assert (
        "/mnt/storage/configs/atlas/source/"
        "generations/$deployment_id"
        in service
    )

    assert (
        'exec "$runtime/scripts/atlas" scheduler run'
        in service
    )

    assert "/opt/project-atlas" not in service
    assert "ExecStart=/bin/atlas" not in service
def _write_hostile_archive(
    destination: Path,
    *,
    kind: str,
) -> None:
    with tarfile.open(destination, "w:gz") as archive:
        if kind == "traversal":
            info = tarfile.TarInfo("../escape")
            payload = b"escape\n"
            info.size = len(payload)

            import io

            archive.addfile(
                info,
                io.BytesIO(payload),
            )

        elif kind == "symlink":
            info = tarfile.TarInfo("scripts/atlas")
            info.type = tarfile.SYMTYPE
            info.linkname = "/bin/sh"
            archive.addfile(info)

        elif kind == "hardlink":
            info = tarfile.TarInfo("scripts/atlas")
            info.type = tarfile.LNKTYPE
            info.linkname = "VERSION"
            archive.addfile(info)

        else:
            raise AssertionError(kind)


def _prepare_verified_hostile_record(
    *,
    runtime: Path,
    deployment_id: str,
    archive_kind: str,
) -> None:
    record = (
        runtime
        / "deployments"
        / "records"
        / deployment_id
    )

    record.mkdir(parents=True)

    (record / "status").write_text(
        "verified\n",
        encoding="utf-8",
    )

    _write_hostile_archive(
        record / "core-source.tar.gz",
        kind=archive_kind,
    )


def test_runtime_source_rejects_path_traversal_before_current_advances(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"

    project.mkdir()
    runtime.mkdir()

    deployment_id = "update-test"

    _prepare_verified_hostile_record(
        runtime=runtime,
        deployment_id=deployment_id,
        archive_kind="traversal",
    )

    result = _run_harness(
        project=project,
        runtime=runtime,
        deployment_id=deployment_id,
    )

    assert result.returncode != 0
    assert "unsafe runtime-source archive member path" in result.stderr

    assert not (
        runtime
        / "deployments"
        / "current"
    ).exists()

    assert not (
        tmp_path
        / "escape"
    ).exists()


def test_runtime_source_rejects_symlink_before_current_advances(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"

    project.mkdir()
    runtime.mkdir()

    deployment_id = "update-test"

    _prepare_verified_hostile_record(
        runtime=runtime,
        deployment_id=deployment_id,
        archive_kind="symlink",
    )

    result = _run_harness(
        project=project,
        runtime=runtime,
        deployment_id=deployment_id,
    )

    assert result.returncode != 0
    assert "runtime-source archive links are not allowed" in result.stderr

    assert not (
        runtime
        / "deployments"
        / "current"
    ).exists()


def test_runtime_source_rejects_hardlink_before_current_advances(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"

    project.mkdir()
    runtime.mkdir()

    deployment_id = "update-test"

    _prepare_verified_hostile_record(
        runtime=runtime,
        deployment_id=deployment_id,
        archive_kind="hardlink",
    )

    result = _run_harness(
        project=project,
        runtime=runtime,
        deployment_id=deployment_id,
    )

    assert result.returncode != 0
    assert "runtime-source archive links are not allowed" in result.stderr

    assert not (
        runtime
        / "deployments"
        / "current"
    ).exists()


def test_runtime_source_root_symlink_is_rejected_before_use(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    outside = tmp_path / "outside"

    project.mkdir()
    runtime.mkdir()
    outside.mkdir()

    deployment_id = "update-test"

    source = tmp_path / "source"
    source.mkdir()
    _write_source_tree(source)

    record = (
        runtime
        / "deployments"
        / "records"
        / deployment_id
    )
    record.mkdir(parents=True)

    (record / "status").write_text(
        "verified\n",
        encoding="utf-8",
    )

    _archive_source(
        source,
        record / "core-source.tar.gz",
    )

    (
        runtime
        / "source"
    ).symlink_to(
        outside,
        target_is_directory=True,
    )

    result = _run_harness(
        project=project,
        runtime=runtime,
        deployment_id=deployment_id,
    )

    assert result.returncode != 0
    assert "runtime-source root must be a regular directory" in result.stderr

    assert not (
        outside
        / "generations"
    ).exists()

    assert not (
        runtime
        / "deployments"
        / "current"
    ).exists()
