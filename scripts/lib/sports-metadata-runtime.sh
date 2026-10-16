#!/usr/bin/env bash

atlas_sports_metadata_runtime_provision() {
  ATLAS_RUNTIME_CONFIG_DIR="${ATLAS_RUNTIME_CONFIG_DIR:-/mnt/storage/configs/atlas}" \
  python3 "$ATLAS_PROJECT_DIR/scripts/lib/sports-metadata-runtime.py" \
    provision "$ATLAS_PROJECT_DIR" \
    "${ATLAS_RUNTIME_CONFIG_DIR:-/mnt/storage/configs/atlas}"
}
