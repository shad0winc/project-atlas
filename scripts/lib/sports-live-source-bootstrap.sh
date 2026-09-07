#!/usr/bin/env bash

ATLAS_SPORTS_LIVE_SOURCE_PATH="${ATLAS_SPORTS_LIVE_SOURCE_PATH:-/mnt/storage/configs/sportyfin/state/live-sources.json}"
ATLAS_SPORTS_LIVE_SOURCE_UID="${ATLAS_SPORTS_LIVE_SOURCE_UID:-1000}"
ATLAS_SPORTS_LIVE_SOURCE_GID="${ATLAS_SPORTS_LIVE_SOURCE_GID:-1000}"


atlas_sports_live_source_bootstrap_provision() {
  local path="$ATLAS_SPORTS_LIVE_SOURCE_PATH"
  local uid="$ATLAS_SPORTS_LIVE_SOURCE_UID"
  local gid="$ATLAS_SPORTS_LIVE_SOURCE_GID"
  local sports_source="$ATLAS_PROJECT_DIR/modules/sports/src"

  [[ -n "$path" && "$path" == /* ]] || {
    printf 'ERROR: Sports live-source bootstrap path must be absolute: %s\n' \
      "$path" >&2
    return 1
  }

  [[ "$uid" =~ ^[0-9]+$ && "$gid" =~ ^[0-9]+$ ]] || {
    echo 'ERROR: Sports live-source bootstrap uid/gid must be numeric.' >&2
    return 1
  }

  [[ -d "$sports_source" ]] || {
    echo 'ERROR: Sports live-source source directory is unavailable.' >&2
    return 1
  }

  ATLAS_SPORTS_LIVE_SOURCE_PATH="$path" \
  ATLAS_SPORTS_LIVE_SOURCE_UID="$uid" \
  ATLAS_SPORTS_LIVE_SOURCE_GID="$gid" \
  PYTHONPATH="$sports_source${PYTHONPATH:+:$PYTHONPATH}" \
  python3 - <<'PY'
from __future__ import annotations

import os
import stat
from pathlib import Path

from live_sources import LiveSourceRegistry


path = Path(os.environ["ATLAS_SPORTS_LIVE_SOURCE_PATH"])
uid = int(os.environ["ATLAS_SPORTS_LIVE_SOURCE_UID"])
gid = int(os.environ["ATLAS_SPORTS_LIVE_SOURCE_GID"])

if path.is_symlink():
    raise SystemExit(
        f"ERROR: Sports live-source bootstrap path is symbolic: {path}"
    )

path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

if os.geteuid() == 0:
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)
else:
    if os.geteuid() != uid or os.getegid() != gid:
        raise SystemExit(
            "ERROR: Sports live-source bootstrap cannot assume "
            "the requested writer identity."
        )

registry = LiveSourceRegistry(path)
registry.ensure()

# ensure() validates existing state instead of overwriting it.
sources = registry.list_sources()

for checked in (path, registry.lock_path):
    info = checked.stat()

    if info.st_uid != uid or info.st_gid != gid:
        raise SystemExit(
            "ERROR: Sports live-source bootstrap ownership mismatch "
            f"for {checked}: {info.st_uid}:{info.st_gid}"
        )

    mode = stat.S_IMODE(info.st_mode)

    if mode != 0o600:
        raise SystemExit(
            "ERROR: Sports live-source bootstrap mode mismatch "
            f"for {checked}: {mode:o}"
        )

print(f"SPORTS_LIVE_SOURCE_BOOTSTRAP_COUNT={len(sources)}")
print("SPORTS_LIVE_SOURCE_BOOTSTRAP_STATE=PASS")
PY
}


atlas_sports_live_source_bootstrap_verify() {
  atlas_sports_live_source_bootstrap_provision
}
