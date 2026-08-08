#!/usr/bin/env bash

# Canonical M-023.25 recovery-state registry.
#
# Columns:
#   surface | source | archive path | requirement | kind | consistency group
#
# This registry describes recovery ownership only. It does not copy, archive,
# delete, or restore state.

atlas_backup_recovery_surface_rows() {
  local sports_root

  : "${ATLAS_CONFIG_ROOT:?ATLAS_CONFIG_ROOT is required}"
  : "${ATLAS_RUNTIME_CONFIG_DIR:?ATLAS_RUNTIME_CONFIG_DIR is required}"
  : "${ATLAS_USERS_DIR:?ATLAS_USERS_DIR is required}"
  : "${ATLAS_IDENTITY_DIR:?ATLAS_IDENTITY_DIR is required}"
  : "${ATLAS_REQUESTS_DIR:?ATLAS_REQUESTS_DIR is required}"
  : "${ATLAS_SCHEDULER_STATE_FILE:?ATLAS_SCHEDULER_STATE_FILE is required}"
  : "${ATLAS_ARI_DIR:?ATLAS_ARI_DIR is required}"

  sports_root="${SPORTS_CONFIG_DIR:-${ATLAS_CONFIG_ROOT}/sportyfin}"

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'users' \
    "$ATLAS_USERS_DIR" \
    'state/users' \
    'required' \
    'directory' \
    'identity'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'identity-invitations' \
    "$ATLAS_IDENTITY_DIR/invitations" \
    'state/identity/invitations' \
    'optional' \
    'directory' \
    'identity'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'favorites' \
    "$ATLAS_IDENTITY_DIR/favorites" \
    'state/identity/favorites' \
    'required' \
    'directory' \
    'identity'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'requests' \
    "$ATLAS_REQUESTS_DIR/requests.json" \
    'state/requests/requests.json' \
    'optional' \
    'file' \
    'requests'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'scheduler' \
    "$ATLAS_SCHEDULER_STATE_FILE" \
    'state/scheduler/tasks.json' \
    'required' \
    'file' \
    'scheduler'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'runtime-events' \
    "$ATLAS_RUNTIME_CONFIG_DIR/runtime/events.jsonl" \
    'state/runtime/events.jsonl' \
    'required' \
    'file' \
    'runtime-events'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'runtime-subscribers' \
    "$ATLAS_RUNTIME_CONFIG_DIR/runtime/subscribers" \
    'state/runtime/subscribers' \
    'required' \
    'directory' \
    'runtime-events'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'retention' \
    "$ATLAS_ARI_DIR" \
    'state/retention' \
    'required' \
    'directory' \
    'retention'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'sports-subscriptions' \
    "$sports_root/state/subscriptions.json" \
    'state/sports/subscriptions.json' \
    'required' \
    'file' \
    'sports'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'sports-recordings' \
    "$sports_root/recordings/recordings.json" \
    'state/sports/recordings.json' \
    'required' \
    'file' \
    'sports'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'sports-scheduler' \
    "$ATLAS_RUNTIME_CONFIG_DIR/runtime/scheduler/sports.json" \
    'state/sports/scheduler.json' \
    'required' \
    'file' \
    'sports'
}

atlas_backup_recovery_validate_registry() {
  local surface source archive requirement kind group
  local count=0
  declare -A seen_surfaces=()
  declare -A seen_archives=()

  while IFS=$'\t' read -r \
    surface source archive requirement kind group
  do
    [[ -n "$surface" && -n "$source" && -n "$archive" ]] || {
      echo 'ERROR: recovery registry contains an incomplete row.' >&2
      return 1
    }

    [[ "$surface" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
      printf 'ERROR: invalid recovery surface: %s\n' "$surface" >&2
      return 1
    }

    [[ "$source" == /* ]] || {
      printf 'ERROR: recovery source is not absolute: %s\n' "$source" >&2
      return 1
    }

    [[ "$archive" == state/* && "$archive" != /* ]] || {
      printf 'ERROR: invalid recovery archive path: %s\n' "$archive" >&2
      return 1
    }

    [[ "/$archive/" != *'/../'* && "/$archive/" != *'/./'* ]] || {
      printf 'ERROR: unsafe recovery archive path: %s\n' "$archive" >&2
      return 1
    }

    [[ "$requirement" == 'required' || "$requirement" == 'optional' ]] || {
      printf 'ERROR: invalid recovery requirement: %s\n' "$requirement" >&2
      return 1
    }

    [[ "$kind" == 'file' || "$kind" == 'directory' ]] || {
      printf 'ERROR: invalid recovery source kind: %s\n' "$kind" >&2
      return 1
    }

    [[ "$group" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
      printf 'ERROR: invalid recovery consistency group: %s\n' "$group" >&2
      return 1
    }

    [[ -z "${seen_surfaces[$surface]+x}" ]] || {
      printf 'ERROR: duplicate recovery surface: %s\n' "$surface" >&2
      return 1
    }

    [[ -z "${seen_archives[$archive]+x}" ]] || {
      printf 'ERROR: duplicate recovery archive path: %s\n' "$archive" >&2
      return 1
    }

    seen_surfaces[$surface]=1
    seen_archives[$archive]=1
    count=$((count + 1))
  done < <(atlas_backup_recovery_surface_rows)

  [[ "$count" -eq 11 ]] || {
    printf 'ERROR: expected 11 recovery surfaces, found %s.\n' "$count" >&2
    return 1
  }
}


# M-023.25.3.2 consistent state snapshot support.
#
# Each consistency group is fingerprinted before and after it is copied. If
# the source changes during the copy, the whole group is retried. A backup is
# rejected after the configured retry limit instead of publishing a mixed
# recovery point.

atlas_backup_recovery_digest_path() {
  local source="$1"
  local kind="$2"
  local material digest entry relative entry_digest

  [[ ! -L "$source" ]] || {
    printf 'ERROR: recovery source is a symbolic link: %s\n' "$source" >&2
    return 1
  }

  if [[ "$kind" == 'file' ]]; then
    [[ -f "$source" ]] || {
      printf 'ERROR: recovery file is unavailable: %s\n' "$source" >&2
      return 1
    }

    digest="$(sha256sum -- "$source" | awk '{print $1}')" || return 1
    printf 'file:%s\n' "$digest"
    return 0
  fi

  [[ "$kind" == 'directory' && -d "$source" ]] || {
    printf 'ERROR: recovery directory is unavailable: %s\n' "$source" >&2
    return 1
  }

  material="$(
    cd "$source" || exit 1

    while IFS= read -r -d '' entry; do
      relative="${entry#./}"

      if [[ -L "$entry" ]]; then
        printf 'ERROR: recovery directory contains symbolic link: %s/%s\n' \
          "$source" "$relative" >&2
        exit 1
      fi

      if [[ -d "$entry" ]]; then
        printf 'directory\t%s\n' "$relative"
        continue
      fi

      if [[ -f "$entry" ]]; then
        entry_digest="$(sha256sum -- "$entry" | awk '{print $1}')" || exit 1
        printf 'file\t%s\t%s\n' "$relative" "$entry_digest"
        continue
      fi

      printf 'ERROR: unsupported recovery filesystem entry: %s/%s\n' \
        "$source" "$relative" >&2
      exit 1
    done < <(find . -mindepth 1 -print0 | LC_ALL=C sort -z)
  )" || return 1

  printf '%s' "$material" |
    sha256sum |
    awk '{print "directory:" $1}'
}

atlas_backup_recovery_group_fingerprint() {
  local wanted_group="$1"
  local surface source archive requirement kind group digest
  local material=''

  while IFS=$'\t' read -r \
    surface source archive requirement kind group
  do
    [[ "$group" == "$wanted_group" ]] || continue

    if [[ ! -e "$source" && ! -L "$source" ]]; then
      if [[ "$requirement" == 'optional' ]]; then
        material+="${surface}"$'\tabsent\n'
        continue
      fi

      printf 'ERROR: required recovery surface is unavailable: %s (%s)\n' \
        "$surface" "$source" >&2
      return 1
    fi

    if [[ "$kind" == 'file' && ! -f "$source" ]] ||
       [[ "$kind" == 'directory' && ! -d "$source" ]]
    then
      printf 'ERROR: recovery source kind mismatch: %s (%s)\n' \
        "$surface" "$source" >&2
      return 1
    fi

    digest="$(atlas_backup_recovery_digest_path "$source" "$kind")" ||
      return 1

    material+="${surface}"$'\t'"${digest}"$'\n'
  done < <(atlas_backup_recovery_surface_rows)

  printf '%s' "$material" |
    sha256sum |
    awk '{print $1}'
}

atlas_backup_recovery_copy_group() {
  local wanted_group="$1"
  local destination="$2"
  local surface source archive requirement kind group target

  while IFS=$'\t' read -r \
    surface source archive requirement kind group
  do
    [[ "$group" == "$wanted_group" ]] || continue

    if [[ ! -e "$source" && ! -L "$source" ]]; then
      [[ "$requirement" == 'optional' ]] || {
        printf 'ERROR: required recovery surface disappeared: %s\n' \
          "$surface" >&2
        return 1
      }
      continue
    fi

    target="$destination/$archive"
    mkdir -p "$(dirname "$target")"
    cp -a -- "$source" "$target" || {
      printf 'ERROR: unable to snapshot recovery surface: %s\n' \
        "$surface" >&2
      return 1
    }
  done < <(atlas_backup_recovery_surface_rows)
}

atlas_backup_recovery_after_group_copy() {
  # Intentional no-op seam used by deterministic consistency-window tests.
  :
}

atlas_backup_recovery_publish_group() {
  local wanted_group="$1"
  local staged="$2"
  local destination="$3"
  local surface source archive requirement kind group staged_path target

  while IFS=$'\t' read -r \
    surface source archive requirement kind group
  do
    [[ "$group" == "$wanted_group" ]] || continue

    staged_path="$staged/$archive"
    [[ -e "$staged_path" ]] || continue

    target="$destination/$archive"
    mkdir -p "$(dirname "$target")"
    cp -a -- "$staged_path" "$target" || {
      printf 'ERROR: unable to publish recovery snapshot surface: %s\n' \
        "$surface" >&2
      return 1
    }
  done < <(atlas_backup_recovery_surface_rows)
}

atlas_backup_recovery_snapshot_group() {
  local group="$1"
  local destination="$2"
  local max_attempts="${ATLAS_BACKUP_SNAPSHOT_ATTEMPTS:-3}"
  local attempt=1 before after work

  [[ "$max_attempts" =~ ^[1-9][0-9]*$ ]] || {
    echo 'ERROR: ATLAS_BACKUP_SNAPSHOT_ATTEMPTS must be a positive integer.' >&2
    return 1
  }

  while (( attempt <= max_attempts )); do
    before="$(atlas_backup_recovery_group_fingerprint "$group")" || return 1

    work="$(mktemp -d "${destination}.group-${group}.XXXXXX")" || return 1
    chmod 0700 "$work" || {
      rm -rf -- "$work"
      return 1
    }

    if ! atlas_backup_recovery_copy_group "$group" "$work"; then
      rm -rf -- "$work"
      return 1
    fi

    atlas_backup_recovery_after_group_copy "$group" "$attempt"

    after="$(atlas_backup_recovery_group_fingerprint "$group")" || {
      rm -rf -- "$work"
      return 1
    }

    if [[ "$before" == "$after" ]]; then
      atlas_backup_recovery_publish_group "$group" "$work" "$destination" || {
        rm -rf -- "$work"
        return 1
      }
      rm -rf -- "$work"
      return 0
    fi

    rm -rf -- "$work"
    printf 'NOTICE: recovery consistency group changed during snapshot; retrying: %s (%s/%s)\n' \
      "$group" "$attempt" "$max_attempts" >&2
    attempt=$((attempt + 1))
  done

  printf 'ERROR: recovery consistency group did not stabilize: %s\n' \
    "$group" >&2
  return 1
}

atlas_backup_recovery_snapshot_state() {
  local destination="$1"
  local surface source archive requirement kind group
  local -a groups=()
  declare -A seen_groups=()

  [[ "$destination" == /* ]] || {
    echo 'ERROR: recovery snapshot destination must be absolute.' >&2
    return 1
  }

  atlas_backup_recovery_validate_registry || return 1

  mkdir -p "$destination/state"
  chmod 0700 "$destination" "$destination/state"

  while IFS=$'\t' read -r \
    surface source archive requirement kind group
  do
    if [[ -z "${seen_groups[$group]+x}" ]]; then
      groups+=("$group")
      seen_groups[$group]=1
    fi
  done < <(atlas_backup_recovery_surface_rows)

  for group in "${groups[@]}"; do
    atlas_backup_recovery_snapshot_group "$group" "$destination" || return 1
  done

  while IFS=$'\t' read -r \
    surface source archive requirement kind group
  do
    if [[ -e "$destination/$archive" ]]; then
      printf '%s\t%s\t%s\t%s\n' \
        "$surface" "$archive" "$requirement" 'captured-unverified'
    elif [[ "$requirement" == 'optional' && ! -e "$source" ]]; then
      printf '%s\t%s\t%s\t%s\n' \
        "$surface" "$archive" "$requirement" 'absent-optional'
    else
      printf 'ERROR: recovery snapshot is missing surface after capture: %s\n' \
        "$surface" >&2
      return 1
    fi
  done < <(atlas_backup_recovery_surface_rows)
}
