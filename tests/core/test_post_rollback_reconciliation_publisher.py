from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = PROJECT_ROOT / "scripts" / "commands" / "deployment.sh"


def test_reconciliation_publisher_returns_only_identifier_and_builds_verified_record(
    tmp_path: Path,
) -> None:
    deployment_root = tmp_path / "deployments"
    records = deployment_root / "records"
    records.mkdir(parents=True)

    previous_id = "baseline-test"
    failed_id = "update-test"
    reconciliation_id = "baseline-reconciliation-test"

    previous = records / previous_id
    failed = records / failed_id
    recovery = failed / "recovery-ingress.test"
    expected_record = records / reconciliation_id

    previous.mkdir()
    failed.mkdir()
    recovery.mkdir()

    (previous / "status").write_text("verified\n", encoding="utf-8")
    (previous / "metadata").write_text(
        "\n".join(
            (
                "type=baseline",
                f"deployment_id={previous_id}",
                "source_commit=source-test",
                "core_commit=core-test",
                "ingress_commit=ingress-test",
                "scope=all",
                "migration=none",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    (previous / "core-source.tar.gz").write_bytes(b"core-source")
    (previous / "ingress-source.tar.gz").write_bytes(b"ingress-source")

    (failed / "metadata").write_text(
        "\n".join(
            (
                "type=update",
                f"deployment_id={failed_id}",
                f"previous_baseline={previous_id}",
                "scope=ingress",
                "migration=none",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    (failed / "status").write_text("failed\n", encoding="utf-8")

    script = r'''
set -euo pipefail

source "$DEPLOYMENT_FILE"

atlas_deployment_new_id() {
  printf '%s\n' "$RECONCILIATION_ID"
}

atlas_deployment_capture_images() {
  local record="$1"

  cat > "$record/images.tsv" <<'EOF'
core|docker-compose.yml|atlas|api|/atlas-api|atlas-api:test|sha256:core-test
ingress|stack/ingress.yml|atlas-ingress|caddy|/atlas-caddy|caddy:test|sha256:ingress-test
EOF
}

atlas_deployment_verify_runtime() {
  local record="$1"
  test -s "$record/images.tsv"
}

output="$(
  atlas_deployment_publish_reconciliation_baseline \
    "$FAILED_ID" \
    "$FAILED_RECORD" \
    "$PREVIOUS_ID" \
    "$PREVIOUS_RECORD" \
    ingress
)"

printf 'CAPTURED_OUTPUT_BEGIN\n'
printf '%s\n' "$output"
printf 'CAPTURED_OUTPUT_END\n'

test "$output" = "$RECONCILIATION_ID"

record="$EXPECTED_RECORD"

test -d "$record"
test "$(cat "$record/status")" = verified

grep -Fxq 'type=baseline' "$record/metadata"
grep -Fxq 'baseline_kind=rollback-reconciliation' "$record/metadata"
grep -Fxq "failed_deployment=$FAILED_ID" "$record/metadata"
grep -Fxq "previous_baseline=$PREVIOUS_ID" "$record/metadata"
grep -Fxq \
  'reason=post-rollback-failure-finalization' \
  "$record/metadata"

test -s "$record/provenance"
test -s "$record/images.tsv"
test -s "$record/core-source.tar.gz"
test -s "$record/ingress-source.tar.gz"
test -s "$record/MANIFEST.sha256"

(
  cd "$record"
  sha256sum -c MANIFEST.sha256 >/dev/null
)
'''

    env = os.environ.copy()
    env.update(
        {
            "ATLAS_DEPLOYMENT_DIR": str(deployment_root),
            "ATLAS_RUNTIME_CONFIG_DIR": str(tmp_path / "runtime-config"),
            "ATLAS_PROJECT_DIR": str(PROJECT_ROOT),
            "DEPLOYMENT_FILE": str(DEPLOYMENT),
            "FAILED_ID": failed_id,
            "FAILED_RECORD": str(failed),
            "PREVIOUS_ID": previous_id,
            "PREVIOUS_RECORD": str(previous),
            "RECONCILIATION_ID": reconciliation_id,
            "EXPECTED_RECORD": str(expected_record),
        }
    )

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, (
        f"publisher contract failed with rc={result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _write_failed_rollback_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, str, str]:
    deployment_root = tmp_path / "deployments"
    records = deployment_root / "records"
    records.mkdir(parents=True)

    previous_id = "baseline-test"
    failed_id = "update-test"

    previous = records / previous_id
    failed = records / failed_id

    previous.mkdir()
    failed.mkdir()
    (failed / "recovery-ingress.test").mkdir()

    (previous / "status").write_text("verified\n", encoding="utf-8")
    (previous / "metadata").write_text(
        "\n".join(
            (
                "type=baseline",
                f"deployment_id={previous_id}",
                "source_commit=source-test",
                "core_commit=core-test",
                "ingress_commit=ingress-test",
                "scope=all",
                "migration=none",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    (failed / "status").write_text("failed\n", encoding="utf-8")
    (failed / "metadata").write_text(
        "\n".join(
            (
                "type=update",
                f"deployment_id={failed_id}",
                f"previous_baseline={previous_id}",
                "target_commit=target-test",
                "core_commit=core-new",
                "ingress_commit=ingress-new",
                "scope=ingress",
                "migration=none",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    maintenance_flag = tmp_path / "maintenance.enabled"
    maintenance_flag.write_text("enabled\n", encoding="utf-8")

    return (
        deployment_root,
        previous,
        failed,
        previous_id,
        failed_id,
    )


def _run_fake_recovery(
    tmp_path: Path,
    *,
    public_verify_fails: bool = False,
    publisher_fails: bool = False,
) -> subprocess.CompletedProcess[str]:
    (
        deployment_root,
        previous,
        failed,
        previous_id,
        failed_id,
    ) = _write_failed_rollback_fixture(tmp_path)

    event_log = tmp_path / "events.log"
    maintenance_flag = tmp_path / "maintenance.enabled"

    script = r'''
set -euo pipefail

source "$DEPLOYMENT_FILE"

atlas_deployment_validate_source() {
  return 0
}

atlas_deployment_current_id() {
  printf '%s\n' "$PREVIOUS_ID"
}

atlas_deployment_lock_dir() {
  printf '%s\n' "$FAKE_LOCK_DIR"
}

atlas_deployment_lock_matches() {
  [[ "$1" == "$FAILED_ID" ]]
}

atlas_maintenance_flag() {
  printf '%s\n' "$MAINTENANCE_FLAG"
}

atlas_deployment_rollback_recovery_source() {
  local transaction="$1"
  local surface="$2"

  test "$surface" = ingress
  printf '%s\n' "$transaction/recovery-ingress.test"
}

atlas_deployment_verify_rollback_runtime() {
  VERIFY_COUNT=$((VERIFY_COUNT + 1))
  printf 'verify:%s\n' "$VERIFY_COUNT" >> "$EVENT_LOG"

  if [[ "$VERIFY_COUNT" -eq 2 && "$PUBLIC_VERIFY_FAILS" == true ]]; then
    return 1
  fi
}

atlas_command_maintenance() {
  local action="$1"
  printf 'maintenance:%s\n' "$action" >> "$EVENT_LOG"

  case "$action" in
    disable)
      rm -f -- "$MAINTENANCE_FLAG"
      ;;
    enable)
      printf 'enabled\n' > "$MAINTENANCE_FLAG"
      ;;
    *)
      return 2
      ;;
  esac
}

atlas_deployment_publish_reconciliation_baseline() {
  printf 'publish\n' >> "$EVENT_LOG"

  if [[ "$PUBLISHER_FAILS" == true ]]; then
    return 1
  fi

  printf '%s\n' "$RECONCILIATION_ID"
}

atlas_deployment_set_current() {
  printf 'set-current:%s\n' "$1" >> "$EVENT_LOG"
}

atlas_deployment_release_lock() {
  printf 'release:%s\n' "$1" >> "$EVENT_LOG"
}

VERIFY_COUNT=0

atlas_deployment_recover_failed_rollback "$FAILED_ID"
'''

    fake_lock_dir = tmp_path / "update.lock"
    fake_lock_dir.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "ATLAS_DEPLOYMENT_DIR": str(deployment_root),
            "ATLAS_RUNTIME_CONFIG_DIR": str(tmp_path / "runtime-config"),
            "ATLAS_PROJECT_DIR": str(PROJECT_ROOT),
            "DEPLOYMENT_FILE": str(DEPLOYMENT),
            "PREVIOUS_ID": previous_id,
            "PREVIOUS_RECORD": str(previous),
            "FAILED_ID": failed_id,
            "FAILED_RECORD": str(failed),
            "FAKE_LOCK_DIR": str(fake_lock_dir),
            "MAINTENANCE_FLAG": str(maintenance_flag),
            "EVENT_LOG": str(event_log),
            "RECONCILIATION_ID": "baseline-reconciliation-test",
            "PUBLIC_VERIFY_FAILS": (
                "true" if public_verify_fails else "false"
            ),
            "PUBLISHER_FAILS": (
                "true" if publisher_fails else "false"
            ),
        }
    )

    result = subprocess.run(
        ["bash", "-c", script],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    events = (
        event_log.read_text(encoding="utf-8")
        if event_log.exists()
        else ""
    )

    # Attach safe test diagnostics to the CompletedProcess instance so each
    # test can assert exact orchestration without touching production state.
    result.events = events  # type: ignore[attr-defined]
    result.maintenance_exists = maintenance_flag.exists()  # type: ignore[attr-defined]

    return result


def test_failed_rollback_recovery_success_orders_finalization_before_release(
    tmp_path: Path,
) -> None:
    result = _run_fake_recovery(tmp_path)

    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}\n"
        f"events:\n{result.events}"
    )

    assert result.events.splitlines() == [
        "verify:1",
        "maintenance:disable",
        "verify:2",
        "publish",
        "set-current:baseline-reconciliation-test",
        "release:update-test",
    ]

    assert result.maintenance_exists is False
    assert "Failed-rollback recovery complete" in result.stdout


def test_failed_rollback_public_verify_failure_reenables_and_retains_lock(
    tmp_path: Path,
) -> None:
    result = _run_fake_recovery(
        tmp_path,
        public_verify_fails=True,
    )

    assert result.returncode != 0

    assert result.events.splitlines() == [
        "verify:1",
        "maintenance:disable",
        "verify:2",
        "maintenance:enable",
    ]

    assert "publish" not in result.events
    assert "set-current:" not in result.events
    assert "release:" not in result.events
    assert result.maintenance_exists is True


def test_failed_rollback_publish_failure_reenables_and_retains_lock(
    tmp_path: Path,
) -> None:
    result = _run_fake_recovery(
        tmp_path,
        publisher_fails=True,
    )

    assert result.returncode != 0

    assert result.events.splitlines() == [
        "verify:1",
        "maintenance:disable",
        "verify:2",
        "publish",
        "maintenance:enable",
    ]

    assert "set-current:" not in result.events
    assert "release:" not in result.events
    assert result.maintenance_exists is True
