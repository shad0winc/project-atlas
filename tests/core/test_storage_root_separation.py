"""Storage pool and persistent Atlas state have separate root boundaries."""

from pathlib import Path
import subprocess

PROJECT = Path(__file__).resolve().parents[2]


def test_config_separates_media_data_from_persistent_state() -> None:
    script = r'''
set -euo pipefail

source config/atlas.conf

test "$ATLAS_STORAGE_ROOT" = /mnt/storage
test "$ATLAS_DATA_ROOT" = /mnt/atlas-pool
test "$ATLAS_MEDIA_ROOT" = /mnt/atlas-pool/media
test "$ATLAS_DOWNLOADS_ROOT" = /mnt/atlas-pool/downloads

test "$ATLAS_BACKUP_DIR" = /mnt/storage/backups/atlas
test "$ATLAS_CONFIG_ROOT" = /mnt/storage/configs
test "$ATLAS_RUNTIME_CONFIG_DIR" = /mnt/storage/configs/atlas

source scripts/commands/verify.sh

atlas_verify_path_within ATLAS_MEDIA_ROOT ATLAS_DATA_ROOT
atlas_verify_path_within ATLAS_DOWNLOADS_ROOT ATLAS_DATA_ROOT
atlas_verify_path_within ATLAS_BACKUP_DIR ATLAS_STORAGE_ROOT
atlas_verify_path_within ATLAS_CONFIG_ROOT ATLAS_STORAGE_ROOT
atlas_verify_path_within ATLAS_RUNTIME_CONFIG_DIR ATLAS_CONFIG_ROOT

if atlas_verify_path_within ATLAS_MEDIA_ROOT ATLAS_STORAGE_ROOT; then
  echo "MEDIA_UNEXPECTEDLY_CONTAINED_IN_PERSISTENT_STORAGE"
  exit 1
fi

# A path outside the selected data root must still be rejected.
ATLAS_MEDIA_ROOT=/mnt/unapproved-media
if atlas_verify_path_within ATLAS_MEDIA_ROOT ATLAS_DATA_ROOT; then
  echo "OUTSIDE_DATA_ROOT_UNEXPECTEDLY_ACCEPTED"
  exit 1
fi

echo "SEPARATE_STORAGE_ROOT_CONTRACT=PASS"
'''
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_configuration_gate_enforces_separate_roots() -> None:
    """Check the configuration gate, not just its containment helper."""
    script = r'''
set -euo pipefail

source config/atlas.conf
source scripts/commands/verify.sh

# Isolate the configuration gate from presentation functions.
atlas_section() { :; }
atlas_ok() { :; }
atlas_fail() { :; }

ATLAS_VERIFY_PASS=true
atlas_verify_configuration >/dev/null

if [[ "$ATLAS_VERIFY_PASS" != true ]]; then
  echo "VALID_SPLIT_ROOTS_REJECTED"
  exit 1
fi

echo "VALID_SPLIT_ROOTS=PASS"

original_media="$ATLAS_MEDIA_ROOT"
original_downloads="$ATLAS_DOWNLOADS_ROOT"
original_backup="$ATLAS_BACKUP_DIR"
original_config="$ATLAS_CONFIG_ROOT"

check_rejected() {
  local label="$1"

  ATLAS_VERIFY_PASS=true
  atlas_verify_configuration >/dev/null

  if [[ "$ATLAS_VERIFY_PASS" != false ]]; then
    printf 'OUTSIDE_ROOT_ACCEPTED=%s\n' "$label"
    exit 1
  fi

  printf 'OUTSIDE_ROOT_REJECTED=%s\n' "$label"
}

ATLAS_MEDIA_ROOT=/mnt/unapproved-media
check_rejected media
ATLAS_MEDIA_ROOT="$original_media"

ATLAS_DOWNLOADS_ROOT=/mnt/unapproved-downloads
check_rejected downloads
ATLAS_DOWNLOADS_ROOT="$original_downloads"

ATLAS_BACKUP_DIR=/mnt/unapproved-backups
check_rejected backup
ATLAS_BACKUP_DIR="$original_backup"

ATLAS_CONFIG_ROOT=/mnt/unapproved-config
check_rejected config
ATLAS_CONFIG_ROOT="$original_config"

ATLAS_VERIFY_PASS=true
atlas_verify_configuration >/dev/null

if [[ "$ATLAS_VERIFY_PASS" != true ]]; then
  echo "RESTORED_SPLIT_ROOTS_REJECTED"
  exit 1
fi

echo "CONFIGURATION_GATE_ROOT_SEPARATION=PASS"
'''
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "CONFIGURATION_GATE_ROOT_SEPARATION=PASS" in result.stdout
