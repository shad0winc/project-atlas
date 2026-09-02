#!/usr/bin/env bash
set -euo pipefail

ATLAS_PROJECT_DIR="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." \
  && pwd
)"

RUNTIME_DIR="${ATLAS_DOWNLOADS_RUNTIME_DIR:-/mnt/storage/configs/atlas/runtime/downloads}"
RUNTIME_FILE="${ATLAS_DOWNLOADS_SNAPSHOT_PATH:-$RUNTIME_DIR/latest.json}"
QBITTORRENT_BASE_URL="${ATLAS_QBITTORRENT_BASE_URL:-http://127.0.0.1:${QBITTORRENT_PORT:-8080}}"

usage() {
  cat <<'EOF'
Usage:
  atlas downloads-runtime publish

Publish the normalized read-only Downloads runtime snapshot.
Requires ATLAS_QBITTORRENT_USERNAME, ATLAS_QBITTORRENT_PASSWORD, and ATLAS_DOWNLOADS_JOB_ID_KEY.
EOF
}

publish() {
  : "${ATLAS_QBITTORRENT_USERNAME:?ATLAS_QBITTORRENT_USERNAME is required}"
  : "${ATLAS_QBITTORRENT_PASSWORD:?ATLAS_QBITTORRENT_PASSWORD is required}"
  : "${ATLAS_DOWNLOADS_JOB_ID_KEY:?ATLAS_DOWNLOADS_JOB_ID_KEY is required}"

  if [[ "$ATLAS_QBITTORRENT_USERNAME" == 'CHANGE_ME' ]]; then
    echo 'ERROR: ATLAS_QBITTORRENT_USERNAME is still the example placeholder.' >&2
    return 2
  fi

  if [[ "$ATLAS_QBITTORRENT_PASSWORD" == 'CHANGE_ME' ]]; then
    echo 'ERROR: ATLAS_QBITTORRENT_PASSWORD is still the example placeholder.' >&2
    return 2
  fi

  if [[ "$ATLAS_DOWNLOADS_JOB_ID_KEY" == 'CHANGE_ME' ]]; then
    echo 'ERROR: ATLAS_DOWNLOADS_JOB_ID_KEY is still the example placeholder.' >&2
    return 2
  fi

  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  ATLAS_DOWNLOADS_SNAPSHOT_PATH="$RUNTIME_FILE" \
  ATLAS_QBITTORRENT_BASE_URL="$QBITTORRENT_BASE_URL" \
  ATLAS_QBITTORRENT_USERNAME="$ATLAS_QBITTORRENT_USERNAME" \
  ATLAS_QBITTORRENT_PASSWORD="$ATLAS_QBITTORRENT_PASSWORD" \
  ATLAS_DOWNLOADS_JOB_ID_KEY="$ATLAS_DOWNLOADS_JOB_ID_KEY" \
  python3 - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

from atlas.downloads import QBittorrentReadOnlyClient, publish_snapshot

client = QBittorrentReadOnlyClient(
    os.environ["ATLAS_QBITTORRENT_BASE_URL"],
    os.environ["ATLAS_QBITTORRENT_USERNAME"],
    os.environ["ATLAS_QBITTORRENT_PASSWORD"],
    job_id_key=os.environ["ATLAS_DOWNLOADS_JOB_ID_KEY"],
)
snapshot = client.collect()
published = publish_snapshot(
    snapshot.to_dict(),
    Path(os.environ["ATLAS_DOWNLOADS_SNAPSHOT_PATH"]),
)
print(f"Downloads runtime snapshot published: {published}")
PY
}

case "${1:-}" in
  publish)
    publish
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "Unknown downloads-runtime command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
