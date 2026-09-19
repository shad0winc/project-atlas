from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = (
    ROOT / "tests/core/test_failed_after_apply_recovery.py"
)

COMMIT = "c" * 40

IMAGE_ROW = (
    "notifications|modules/notifications/docker-compose.yml|"
    "notifications|atlas-notifications-worker|"
    "/atlas-notifications-worker|"
    "notifications:test|sha256:notifications-test"
)

ARCHIVE = b"recorded-notifications-source\n"


@pytest.fixture
def recovery_fixture_module():
    # Reuse the already-tested isolated recovery harness. Its shell
    # functions mock runtime verification, maintenance, and pointer
    # publication; all record paths are under pytest's tmp_path.
    spec = importlib.util.spec_from_file_location(
        "atlas_failed_after_apply_test_fixture",
        FIXTURE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_adopted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recovery_fixture_module,
    *,
    mode: str = "matching",
    private_runtime_fails: bool = False,
    public_runtime_fails: bool = False,
):
    module = recovery_fixture_module
    original = module._write_failed_after_apply_fixture

    def adopted_fixture(path: Path, **kwargs):
        fixture = original(path, **kwargs)
        transaction = fixture["failed"]

        with (transaction / "metadata").open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(f"notifications_commit={COMMIT}\n")

        (transaction / "notifications-source.tar.gz").write_bytes(
            ARCHIVE
        )
        (transaction / "notifications-image.tsv").write_text(
            IMAGE_ROW + "\n", encoding="utf-8"
        )
        (transaction / "notifications-source-commit").write_text(
            COMMIT + "\n", encoding="utf-8"
        )

        with (transaction / "images.tsv").open(
            "a", encoding="utf-8"
        ) as stream:
            stream.write(IMAGE_ROW + "\n")

        if mode == "missing-archive":
            (transaction / "notifications-source.tar.gz").unlink()
        elif mode == "wrong-source-commit":
            (
                transaction / "notifications-source-commit"
            ).write_text("d" * 40 + "\n", encoding="utf-8")
        elif mode == "wrong-image-row":
            (
                transaction / "notifications-image.tsv"
            ).write_text(
                IMAGE_ROW.replace(
                    "sha256:notifications-test",
                    "sha256:different-image",
                ) + "\n",
                encoding="utf-8",
            )
        elif mode == "missing-manifest-row":
            (transaction / "images.tsv").write_text(
                (transaction / "images.tsv")
                .read_text(encoding="utf-8")
                .replace(IMAGE_ROW + "\n", ""),
                encoding="utf-8",
            )
        elif mode != "matching":
            raise AssertionError(f"unsupported fixture mode: {mode}")

        return fixture

    monkeypatch.setattr(
        module,
        "_write_failed_after_apply_fixture",
        adopted_fixture,
    )

    return module._run_failed_after_apply_recovery(
        tmp_path,
        private_runtime_fails=private_runtime_fails,
        public_runtime_fails=public_runtime_fails,
    )


def assert_preserved_failure(result) -> None:
    assert result.returncode != 0
    assert result.current_id == "baseline-test"
    assert result.failed_status == "failed"
    assert result.lock_exists is True
    assert result.maintenance_exists is True
    assert result.reconciliation.exists() is False
    assert "set-current:" not in result.events
    assert "release:" not in result.events


def test_adopted_failed_after_apply_preserves_recorded_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recovery_fixture_module,
) -> None:
    result = run_adopted(
        tmp_path, monkeypatch, recovery_fixture_module
    )

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert result.current_id == "baseline-reconciliation-test"
    assert result.failed_status == "failed"
    assert result.lock_exists is False
    assert result.maintenance_exists is False

    record = result.reconciliation
    assert record.is_dir()

    metadata = (record / "metadata").read_text(
        encoding="utf-8"
    )
    provenance = (record / "provenance").read_text(
        encoding="utf-8"
    )

    assert f"notifications_commit={COMMIT}\n" in metadata
    assert f"notifications_commit={COMMIT}\n" in provenance

    assert (
        record / "notifications-source.tar.gz"
    ).read_bytes() == ARCHIVE

    assert (
        record / "notifications-source-commit"
    ).read_text(encoding="utf-8") == COMMIT + "\n"

    assert (
        record / "notifications-image.tsv"
    ).read_text(encoding="utf-8") == IMAGE_ROW + "\n"

    assert (
        IMAGE_ROW + "\n"
        in (record / "images.tsv").read_text(
            encoding="utf-8"
        )
    )

    manifest = (
        record / "MANIFEST.sha256"
    ).read_text(encoding="utf-8")

    for name in (
        "notifications-source.tar.gz",
        "notifications-image.tsv",
        "notifications-source-commit",
    ):
        assert name in manifest

    check = subprocess.run(
        ["sha256sum", "-c", "MANIFEST.sha256"],
        cwd=record,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stderr

    assert result.events.count("runtime-verify:") == 2
    assert result.events.index(
        "runtime-verify:1"
    ) < result.events.index("maintenance:disable")

    assert result.events.index(
        "runtime-verify:2"
    ) < result.events.index(
        "set-current:baseline-reconciliation-test"
    )

    assert result.events.index(
        "set-current:baseline-reconciliation-test"
    ) < result.events.index("release:update-test")


@pytest.mark.parametrize(
    "mode",
    (
        "missing-archive",
        "wrong-source-commit",
        "wrong-image-row",
        "missing-manifest-row",
    ),
)
def test_inconsistent_adopted_evidence_blocks_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recovery_fixture_module,
    mode: str,
) -> None:
    result = run_adopted(
        tmp_path,
        monkeypatch,
        recovery_fixture_module,
        mode=mode,
    )
    assert_preserved_failure(result)
    assert "maintenance:disable" not in result.events
    assert "runtime-verify:" not in result.events


def test_private_runtime_failure_preserves_failed_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recovery_fixture_module,
) -> None:
    result = run_adopted(
        tmp_path,
        monkeypatch,
        recovery_fixture_module,
        private_runtime_fails=True,
    )
    assert_preserved_failure(result)
    assert "runtime-verify:1" in result.events
    assert "maintenance:disable" not in result.events


def test_public_runtime_failure_restores_maintenance_and_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recovery_fixture_module,
) -> None:
    result = run_adopted(
        tmp_path,
        monkeypatch,
        recovery_fixture_module,
        public_runtime_fails=True,
    )
    assert_preserved_failure(result)
    assert "maintenance:disable" in result.events
    assert "runtime-verify:2" in result.events
    assert "maintenance:enable" in result.events
