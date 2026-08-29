#!/usr/bin/env bash
set -euo pipefail

ATLAS_PROJECT_DIR="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." \
  && pwd
)"

RUNTIME_DIR="${ATLAS_SERVICE_LIFECYCLE_RUNTIME_DIR:-/mnt/storage/configs/atlas/runtime/services}"
RUNTIME_FILE="${ATLAS_SERVICE_LIFECYCLE_SNAPSHOT_PATH:-$RUNTIME_DIR/latest.json}"

usage() {
  cat <<'EOF'
Usage:
  atlas service-runtime publish

Publish the normalized read-only Service Lifecycle runtime snapshot.
EOF
}

publish() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  ATLAS_PROJECT_DIR="$ATLAS_PROJECT_DIR" \
  ATLAS_SERVICE_LIFECYCLE_SNAPSHOT_PATH="$RUNTIME_FILE" \
  python3 - <<'PY'
from __future__ import annotations

import os
from pathlib import Path

from atlas.service_lifecycle.providers import (
    DockerComposeProvider,
)
from atlas.service_lifecycle.runtime_snapshot import (
    build_runtime_snapshot,
)
from atlas.service_lifecycle.runtime_snapshot_publish import (
    publish_runtime_snapshot,
)


project_root = Path(
    os.environ["ATLAS_PROJECT_DIR"]
)

compose_file = Path(
    os.environ.get(
        "ATLAS_SERVICE_LIFECYCLE_COMPOSE_FILE",
        str(project_root / "docker-compose.yml"),
    )
)

project_directory_value = os.environ.get(
    "ATLAS_SERVICE_LIFECYCLE_PROJECT_DIRECTORY"
)

project_directory = (
    Path(project_directory_value)
    if project_directory_value
    else compose_file.parent
)

destination = Path(
    os.environ[
        "ATLAS_SERVICE_LIFECYCLE_SNAPSHOT_PATH"
    ]
)

provider = DockerComposeProvider(
    compose_file=compose_file,
    project_directory=project_directory,
    environment=os.environ,
)

payload = build_runtime_snapshot(provider)

published = publish_runtime_snapshot(
    payload,
    destination,
)

print(
    "Service Lifecycle runtime snapshot published: "
    f"{published}"
)
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
    echo "Unknown service-runtime command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
