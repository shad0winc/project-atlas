#!/usr/bin/env bash

ATLAS_SPORTS_DISPATCHARR_BINDINGS_PATH="${ATLAS_SPORTS_DISPATCHARR_BINDINGS_PATH:-/mnt/storage/configs/sportyfin/state/dispatcharr-channel-bindings.json}"
ATLAS_SPORTS_DISPATCHARR_BINDINGS_UID="${ATLAS_SPORTS_DISPATCHARR_BINDINGS_UID:-1000}"
ATLAS_SPORTS_DISPATCHARR_BINDINGS_GID="${ATLAS_SPORTS_DISPATCHARR_BINDINGS_GID:-1000}"
ATLAS_SPORTS_DISPATCHARR_BINDINGS_MODE="${ATLAS_SPORTS_DISPATCHARR_BINDINGS_MODE:-600}"

atlas_sports_dispatcharr_binding_bootstrap_provision() {
  local path="$ATLAS_SPORTS_DISPATCHARR_BINDINGS_PATH"
  local uid="$ATLAS_SPORTS_DISPATCHARR_BINDINGS_UID"
  local gid="$ATLAS_SPORTS_DISPATCHARR_BINDINGS_GID"
  local mode="$ATLAS_SPORTS_DISPATCHARR_BINDINGS_MODE"
  local project_dir
  local module_dir

  [[ "$path" == /* ]] || {
    printf \
      'ERROR: Sports Dispatcharr binding bootstrap path must be absolute: %s\n' \
      "$path" >&2
    return 1
  }

  [[ "$uid" =~ ^[0-9]+$ && "$gid" =~ ^[0-9]+$ ]] || {
    echo \
      'ERROR: Sports Dispatcharr binding bootstrap uid/gid must be numeric.' \
      >&2
    return 1
  }

  [[ "$mode" =~ ^[0-7]{3,4}$ ]] || {
    printf \
      'ERROR: Sports Dispatcharr binding bootstrap mode is invalid: %s\n' \
      "$mode" >&2
    return 1
  }

  project_dir="${ATLAS_PROJECT_DIR:-$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &&
      pwd -P
  )}" || return 1

  module_dir="$project_dir/modules/sports/src"

  [[ -f "$module_dir/dispatcharr_channel_bindings.py" ]] || {
    printf \
      'ERROR: Dispatcharr channel binding registry module is unavailable: %s\n' \
      "$module_dir/dispatcharr_channel_bindings.py" >&2
    return 1
  }

  python3 - \
    "$path" \
    "$uid" \
    "$gid" \
    "$mode" \
    "$module_dir" <<'PY'
from __future__ import annotations

import os
from pathlib import Path
import stat
import sys

path = Path(sys.argv[1])
expected_uid = int(sys.argv[2])
expected_gid = int(sys.argv[3])
expected_mode = int(sys.argv[4], 8)
module_dir = Path(sys.argv[5])

lock_path = Path(f"{path}.lock")

if not path.is_absolute():
    raise SystemExit(
        f"ERROR: Sports Dispatcharr binding bootstrap path must be absolute: {path}"
    )

if path.is_symlink():
    raise SystemExit(
        f"ERROR: Sports Dispatcharr binding bootstrap path is symbolic: {path}"
    )

if lock_path.is_symlink():
    raise SystemExit(
        f"ERROR: Sports Dispatcharr binding bootstrap lock is symbolic: {lock_path}"
    )

parent = path.parent

if parent.exists():
    if parent.is_symlink():
        raise SystemExit(
            f"ERROR: Sports Dispatcharr binding bootstrap parent is symbolic: {parent}"
        )
    if not parent.is_dir():
        raise SystemExit(
            f"ERROR: Sports Dispatcharr binding bootstrap parent is not a directory: {parent}"
        )
else:
    parent.mkdir(parents=True, mode=0o755)

existed = path.exists()
lock_existed = lock_path.exists()

sys.path.insert(0, str(module_dir))

from dispatcharr_channel_bindings import (  # noqa: E402
    DispatcharrChannelBindingError,
    DispatcharrChannelBindingRegistry,
)

registry = DispatcharrChannelBindingRegistry(path)

try:
    registry.ensure()
except DispatcharrChannelBindingError as exc:
    raise SystemExit(
        f"ERROR: Sports Dispatcharr binding bootstrap validation failed: {exc}"
    ) from exc
except OSError as exc:
    raise SystemExit(
        f"ERROR: Sports Dispatcharr binding bootstrap failed: {exc}"
    ) from exc

if path.is_symlink() or not path.is_file():
    raise SystemExit(
        f"ERROR: Sports Dispatcharr binding bootstrap did not produce a regular file: {path}"
    )

if lock_path.is_symlink() or not lock_path.is_file():
    raise SystemExit(
        f"ERROR: Sports Dispatcharr binding bootstrap lock is unavailable: {lock_path}"
    )

# Existing authoritative state is never silently repaired. If it already
# exists, validate its access contract and fail closed on drift.
if existed:
    metadata = path.stat()

    if metadata.st_uid != expected_uid or metadata.st_gid != expected_gid:
        raise SystemExit(
            "ERROR: Sports Dispatcharr binding bootstrap ownership mismatch "
            f"for existing state: {path}"
        )

    if stat.S_IMODE(metadata.st_mode) != expected_mode:
        raise SystemExit(
            "ERROR: Sports Dispatcharr binding bootstrap mode mismatch "
            f"for existing state: {path}"
        )
else:
    os.chown(path, expected_uid, expected_gid)
    os.chmod(path, expected_mode)

# The registry uses a durable adjacent lock. A first-deployment bootstrap
# may create it as the deployment user, so make first-use ownership explicit.
if lock_existed:
    metadata = lock_path.stat()

    if metadata.st_uid != expected_uid or metadata.st_gid != expected_gid:
        raise SystemExit(
            "ERROR: Sports Dispatcharr binding bootstrap ownership mismatch "
            f"for existing lock: {lock_path}"
        )

    if stat.S_IMODE(metadata.st_mode) != expected_mode:
        raise SystemExit(
            "ERROR: Sports Dispatcharr binding bootstrap mode mismatch "
            f"for existing lock: {lock_path}"
        )
else:
    os.chown(lock_path, expected_uid, expected_gid)
    os.chmod(lock_path, expected_mode)

# Re-open through the authoritative registry after filesystem provisioning.
try:
    bindings = registry.list_bindings()
except DispatcharrChannelBindingError as exc:
    raise SystemExit(
        f"ERROR: Sports Dispatcharr binding bootstrap verification failed: {exc}"
    ) from exc

print(f"SPORTS_DISPATCHARR_BINDING_BOOTSTRAP_COUNT={len(bindings)}")
print("SPORTS_DISPATCHARR_BINDING_BOOTSTRAP_STATE=PASS")
PY
}


atlas_sports_dispatcharr_binding_bootstrap_verify() {
  atlas_sports_dispatcharr_binding_bootstrap_provision
}
