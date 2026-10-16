#!/usr/bin/env bash

atlas_metadata_recovery_helper() {
  printf '%s/metadata-recovery.py\n' \
    "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
}

atlas_metadata_recovery_capture() {
  local snapshot_root="$1"
  : "${ATLAS_RUNTIME_CONFIG_DIR:?ATLAS_RUNTIME_CONFIG_DIR is required}"
  python3 "$(atlas_metadata_recovery_helper)" capture \
    "$ATLAS_RUNTIME_CONFIG_DIR/private/sports-metadata" \
    "$snapshot_root/metadata-recovery"
}

atlas_metadata_recovery_validate_archive() {
  python3 "$(atlas_metadata_recovery_helper)" validate-archive "$1"
}

atlas_metadata_recovery_validate_staged() {
  python3 "$(atlas_metadata_recovery_helper)" validate-staged "$1"
}
