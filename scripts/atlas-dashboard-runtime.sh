#!/usr/bin/env bash
set -euo pipefail

ATLAS_PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ATLAS_DASHBOARD_RUNTIME_DIR:-/mnt/storage/configs/atlas/runtime/dashboard}"
HEALTH_FILE="${ATLAS_DASHBOARD_HEALTH_SNAPSHOT_PATH:-$RUNTIME_DIR/health.json}"

usage() {
  cat <<'USAGE'
Usage:
  atlas-dashboard-runtime.sh publish-health
  atlas-dashboard-runtime.sh publish-scheduler
  atlas-dashboard-runtime.sh publish-operations
  atlas-dashboard-runtime.sh publish-all

Publish bounded host-authoritative Dashboard runtime projections.
USAGE
}

publish_health() {
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  ATLAS_DASHBOARD_HEALTH_SNAPSHOT_PATH="$HEALTH_FILE" \
  python3 - <<'PY'
import os
from pathlib import Path

from atlas.dashboard_runtime import publish_snapshot
from atlas.health import collect_operational_health

report = collect_operational_health()
destination = Path(os.environ["ATLAS_DASHBOARD_HEALTH_SNAPSHOT_PATH"])
published = publish_snapshot(report.to_dict(), destination)
print(f"Dashboard health runtime snapshot published: {published}")
PY
}


# Scheduler publication helper used by PR61 runtime authority.
publish_scheduler_snapshot() {
  local destination="${ATLAS_DASHBOARD_SCHEDULER_SNAPSHOT_PATH:-${ATLAS_DASHBOARD_RUNTIME_DIR:-/mnt/storage/configs/atlas/runtime/dashboard}/scheduler.json}"
  local state_file="${ATLAS_SCHEDULER_STATE_FILE:-/mnt/storage/configs/atlas/scheduler/tasks.json}"
  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  DASH_DEST="$destination" \
  SCHED_STATE="$state_file" \
  python3 - <<'PYSCHED'
import os
from datetime import datetime, timezone
from pathlib import Path

from atlas.dashboard_runtime import SCHEMA_VERSION, publish_snapshot
from atlas.scheduler import TaskScheduler

tasks = TaskScheduler(Path(os.environ["SCHED_STATE"])).list_tasks()
payload = {
    "schema_version": SCHEMA_VERSION,
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "tasks": tasks,
}
published = publish_snapshot(payload, Path(os.environ["DASH_DEST"]))
print(f"Dashboard scheduler runtime snapshot published: {published}")
PYSCHED
}


# Operations publication helper used by PR61 runtime authority.
publish_operations_snapshot() {
  local source_root="${ATLAS_OPERATIONS_DIRECTORY:-/mnt/storage/configs/atlas/operations}"
  local destination_root="${ATLAS_DASHBOARD_OPERATIONS_RUNTIME_DIR:-${ATLAS_DASHBOARD_RUNTIME_DIR:-/mnt/storage/configs/atlas/runtime/dashboard}/operations}"

  PYTHONPATH="$ATLAS_PROJECT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
  DASH_OPERATIONS_SOURCE="$source_root" \
  DASH_OPERATIONS_DESTINATION="$destination_root" \
  python3 - <<'PYOPS'
import os
from pathlib import Path

from atlas.dashboard_runtime import publish_operations_projection

published = publish_operations_projection(
    Path(os.environ["DASH_OPERATIONS_SOURCE"]),
    Path(os.environ["DASH_OPERATIONS_DESTINATION"]),
    history_limit=2,
)

print(
    "Dashboard Operations runtime projection published: "
    + str(published)
)
PYOPS
}

case "${1:-}" in
  publish-health)
    publish_health
    ;;
  publish-scheduler)
    publish_scheduler_snapshot
    ;;
  publish-operations)
    publish_operations_snapshot
    ;;
  publish-all)
    publish_health
    publish_scheduler_snapshot
    publish_operations_snapshot
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "Unknown dashboard-runtime command: $1" >&2
    usage >&2
    exit 1
    ;;
esac
