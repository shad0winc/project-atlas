#!/usr/bin/env bash

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sports-backend-recovery.sh"

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
    'sports-live-tv-bindings' \
    "$sports_root/state/live-tv-bindings.json" \
    'state/sports/live-tv-bindings.json' \
    'required' \
    'file' \
    'sports'

  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    'sports-source-lifecycle' \
    "$sports_root/state/source-lifecycle.json" \
    'state/sports/source-lifecycle.json' \
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

  [[ "$count" -eq 13 ]] || {
    printf 'ERROR: expected 13 recovery surfaces, found %s.\n' "$count" >&2
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
        "$surface" "$archive" "$requirement" 'captured'
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


# M-023.25.3.3 state-complete archive integrity support.

atlas_backup_recovery_write_snapshot_checksums() {
  local snapshot_root="$1"
  local destination="$2"
  local path relative digest count=0

  [[ -d "$snapshot_root/state" ]] || {
    echo 'ERROR: recovery snapshot state directory is unavailable.' >&2
    return 1
  }

  : > "$destination"
  chmod 0600 "$destination"

  while IFS= read -r -d '' path; do
    [[ ! -L "$path" ]] || {
      printf 'ERROR: checksum source is a symbolic link: %s\n' "$path" >&2
      return 1
    }

    relative="${path#"$snapshot_root"/}"

    [[ "$relative" == state/* &&
       "$relative" != *$'\n'* &&
       "$relative" != *$'\t'* ]] || {
      printf 'ERROR: unsafe recovery checksum path: %s\n' "$relative" >&2
      return 1
    }

    digest="$(sha256sum -- "$path" | awk '{print $1}')" || return 1
    printf '%s  %s\n' "$digest" "$relative" >> "$destination"
    count=$((count + 1))
  done < <(
    find "$snapshot_root/state" -type f -print0 |
      LC_ALL=C sort -z
  )

  [[ "$count" -gt 0 ]] || {
    echo 'ERROR: recovery snapshot contains no checksum-eligible state.' >&2
    return 1
  }
}

atlas_backup_recovery_archive_member_present() {
  local listing="$1"
  local wanted="$2"
  local member

  while IFS= read -r member; do
    [[ "$member" == "$wanted" ||
       "$member" == "$wanted/" ||
       "$member" == "$wanted/"* ]] && return 0
  done <<< "$listing"

  return 1
}

atlas_backup_recovery_validate_archive() {
  local archive="$1"
  local listing recovery_format manifest checksums backup_info
  local header body line surface archive_path requirement policy extra
  local expected_path expected_requirement expected_kind
  local checksum member actual matched captured_path
  local row_count=0 project_rows=0 checksum_count=0
  declare -A registry_path=()
  declare -A registry_requirement=()
  declare -A registry_kind=()
  declare -A seen_surface=()
  declare -A captured_paths=()
  declare -A checksum_members=()

  [[ -f "$archive" && ! -L "$archive" ]] || {
    echo 'ERROR: recovery archive is not a regular file.' >&2
    return 1
  }

  atlas_backup_recovery_validate_registry || return 1

  listing="$(tar -tzf "$archive")" || {
    echo 'ERROR: recovery archive is unreadable.' >&2
    return 1
  }

  while IFS=$'\t' read -r \
    surface _source archive_path requirement expected_kind _group
  do
    registry_path["$surface"]="$archive_path"
    registry_requirement["$surface"]="$requirement"
    registry_kind["$surface"]="$expected_kind"
  done < <(atlas_backup_recovery_surface_rows)

  recovery_format="$(tar -xOzf "$archive" RECOVERY_FORMAT 2>/dev/null)" || {
    echo 'ERROR: recovery archive is missing RECOVERY_FORMAT.' >&2
    return 1
  }

  [[ "$recovery_format" == '1' ||
     "$recovery_format" == '2' ]] || {
    echo 'ERROR: unsupported recovery archive format.' >&2
    return 1
  }

  backup_info="$(tar -xOzf "$archive" BACKUP_INFO.txt 2>/dev/null)" || {
    echo 'ERROR: recovery archive is missing BACKUP_INFO.txt.' >&2
    return 1
  }

  grep -Fxq 'Recovery state: state-complete' <<< "$backup_info" || {
    echo 'ERROR: recovery archive does not declare state completeness.' >&2
    return 1
  }

  grep -Fxq 'Recovery capability: restore-unverified' <<< "$backup_info" || {
    echo 'ERROR: recovery archive restore-verification state is invalid.' >&2
    return 1
  }

  manifest="$(tar -xOzf "$archive" RECOVERY_MANIFEST.tsv 2>/dev/null)" || {
    echo 'ERROR: recovery archive is missing RECOVERY_MANIFEST.tsv.' >&2
    return 1
  }

  header="${manifest%%$'\n'*}"
  [[ "$header" == $'surface\tarchive_path\trequirement\tpolicy' ]] || {
    echo 'ERROR: recovery manifest header is invalid.' >&2
    return 1
  }

  body="${manifest#*$'\n'}"

  while IFS=$'\t' read -r \
    surface archive_path requirement policy extra
  do
    [[ -n "$surface" ]] || continue
    [[ -z "$extra" ]] || {
      echo 'ERROR: recovery manifest row has unexpected fields.' >&2
      return 1
    }

    row_count=$((row_count + 1))

    if [[ "$surface" == 'project-configuration' ]]; then
      [[ "$archive_path" == '.' &&
         "$requirement" == 'required' &&
         "$policy" == 'configuration-only' ]] || {
        echo 'ERROR: project-configuration recovery row is invalid.' >&2
        return 1
      }
      project_rows=$((project_rows + 1))
      continue
    fi

    [[ -n "${registry_path[$surface]+x}" ]] || {
      printf 'ERROR: undeclared recovery manifest surface: %s\n' \
        "$surface" >&2
      return 1
    }

    [[ -z "${seen_surface[$surface]+x}" ]] || {
      printf 'ERROR: duplicate recovery manifest surface: %s\n' \
        "$surface" >&2
      return 1
    }

    expected_path="${registry_path[$surface]}"
    expected_requirement="${registry_requirement[$surface]}"
    expected_kind="${registry_kind[$surface]}"

    [[ "$archive_path" == "$expected_path" &&
       "$requirement" == "$expected_requirement" ]] || {
      printf 'ERROR: recovery manifest contract mismatch: %s\n' \
        "$surface" >&2
      return 1
    }

    case "$policy" in
      captured)
        atlas_backup_recovery_archive_member_present \
          "$listing" "$archive_path" || {
            printf 'ERROR: captured recovery surface is absent: %s\n' \
              "$surface" >&2
            return 1
          }
        captured_paths["$archive_path"]="$expected_kind"
        ;;
      absent-optional)
        [[ "$requirement" == 'optional' ]] || {
          printf 'ERROR: required recovery surface declared absent: %s\n' \
            "$surface" >&2
          return 1
        }
        if atlas_backup_recovery_archive_member_present \
          "$listing" "$archive_path"
        then
          printf 'ERROR: optional-absent surface has archived content: %s\n' \
            "$surface" >&2
          return 1
        fi
        ;;
      *)
        printf 'ERROR: invalid recovery capture policy: %s\n' "$policy" >&2
        return 1
        ;;
    esac

    seen_surface["$surface"]=1
  done <<< "$body"

  [[ "$project_rows" -eq 1 && "$row_count" -eq 14 ]] || {
    echo 'ERROR: recovery manifest row count is invalid.' >&2
    return 1
  }

  for surface in "${!registry_path[@]}"; do
    [[ -n "${seen_surface[$surface]+x}" ]] || {
      printf 'ERROR: recovery manifest omitted surface: %s\n' "$surface" >&2
      return 1
    }
  done

  checksums="$(tar -xOzf "$archive" SHA256SUMS 2>/dev/null)" || {
    echo 'ERROR: recovery archive is missing SHA256SUMS.' >&2
    return 1
  }

  while IFS= read -r line; do
    [[ -n "$line" ]] || continue

    checksum="${line%%  *}"
    member="${line#*  }"

    [[ "$checksum" =~ ^[0-9a-f]{64}$ &&
       "$member" != "$line" &&
       "$member" == state/* &&
       "$member" != /* &&
       "/$member/" != *'/../'* ]] || {
      echo 'ERROR: invalid recovery checksum row.' >&2
      return 1
    }

    [[ -z "${checksum_members[$member]+x}" ]] || {
      printf 'ERROR: duplicate recovery checksum member: %s\n' \
        "$member" >&2
      return 1
    }

    atlas_backup_recovery_archive_member_present "$listing" "$member" || {
      printf 'ERROR: checksummed recovery member is absent: %s\n' \
        "$member" >&2
      return 1
    }

    matched=false
    for captured_path in "${!captured_paths[@]}"; do
      if [[ "$member" == "$captured_path" ||
            "$member" == "$captured_path/"* ]]
      then
        matched=true
        break
      fi
    done

    [[ "$matched" == true ]] || {
      printf 'ERROR: checksummed state is outside declared surfaces: %s\n' \
        "$member" >&2
      return 1
    }

    actual="$(tar -xOzf "$archive" "$member" 2>/dev/null | sha256sum | awk '{print $1}')" || {
      printf 'ERROR: unable to verify recovery checksum: %s\n' "$member" >&2
      return 1
    }

    [[ "$actual" == "$checksum" ]] || {
      printf 'ERROR: recovery checksum mismatch: %s\n' "$member" >&2
      return 1
    }

    checksum_members["$member"]=1
    checksum_count=$((checksum_count + 1))
  done <<< "$checksums"

  [[ "$checksum_count" -gt 0 ]] || {
    echo 'ERROR: recovery checksum manifest is empty.' >&2
    return 1
  }

  while IFS= read -r member; do
    [[ "$member" == state/* && "$member" != */ ]] || continue

    [[ -n "${checksum_members[$member]+x}" ]] || {
      printf 'ERROR: archived state file lacks checksum coverage: %s\n' \
        "$member" >&2
      return 1
    }
  done <<< "$listing"

  for captured_path in "${!captured_paths[@]}"; do
    if [[ "${captured_paths[$captured_path]}" == 'file' ]]; then
      [[ -n "${checksum_members[$captured_path]+x}" ]] || {
        printf 'ERROR: captured recovery file lacks checksum: %s\n' \
          "$captured_path" >&2
        return 1
      }
    fi
  done
  if [[ "$recovery_format" == '2' ]]; then
    atlas_sports_backend_recovery_validate_archive \
      "$archive" || return 1
  fi

}

# M-023.25.5 isolated staged restore support.
#
# Archive validation and member safety are completed before any extraction.
# Extraction is restricted to a newly-created private staging directory and
# never targets an authoritative Atlas state path.

atlas_backup_recovery_validate_safe_members() {
  local archive="$1"

  python3 - "$archive" <<'PY_SAFE_MEMBERS'
import sys
import tarfile

archive_path = sys.argv[1]
allowed_roots = {
    "BACKUP_INFO.txt",
    "RECOVERY_FORMAT",
    "RECOVERY_MANIFEST.tsv",
    "SHA256SUMS",
    "docker-compose.yml",
    "docker-compose.sports.yml",
    ".env.example",
    "VERSION",
    "CHARTER.md",
    "ROADMAP.md",
    "CHANGELOG.md",
    "config",
    "docs",
    "modules",
    "scripts",
    "state",
}

seen: set[str] = set()

try:
    archive = tarfile.open(archive_path, mode="r:gz")
except (OSError, tarfile.TarError) as exc:
    raise SystemExit(f"ERROR: unable to inspect recovery archive members: {exc}")

with archive:
    # Safe-member validation is intentionally usable on malformed/minimal
    # archives independently from the full archive-contract validator.
    #
    # Missing RECOVERY_FORMAT therefore defaults to the historical format-1
    # member allowlist here. Full archive validation is responsible for
    # requiring and validating RECOVERY_FORMAT before staging.
    recovery_format = "1"

    try:
        format_info = archive.getmember("RECOVERY_FORMAT")
    except KeyError:
        format_info = None

    if format_info is not None and format_info.isfile():
        format_member = archive.extractfile(format_info)

        if format_member is not None:
            recovery_format = (
                format_member
                .read()
                .decode("utf-8", errors="strict")
                .strip()
            )

    for member in archive.getmembers():
        name = member.name
        raw = name[:-1] if name.endswith("/") else name

        if (
            not raw
            or name.startswith("/")
            or "\\" in name
            or "\n" in name
            or "\r" in name
            or "\t" in name
            or "\x00" in name
        ):
            raise SystemExit(f"ERROR: unsafe recovery archive member path: {name!r}")

        pieces = raw.split("/")
        if any(piece in {"", ".", ".."} for piece in pieces):
            raise SystemExit(f"ERROR: unsafe recovery archive member path: {name!r}")

        if pieces[0] not in allowed_roots:
            if (
                recovery_format == "2"
                and (
                    name == "backend-recovery"
                    or name.startswith("backend-recovery/")
                )
            ):
                continue

            raise SystemExit(f"ERROR: undeclared recovery archive member: {name}")

        if raw in seen:
            raise SystemExit(f"ERROR: duplicate recovery archive member: {name}")
        seen.add(raw)

        if not (member.isfile() or member.isdir()):
            raise SystemExit(
                f"ERROR: unsupported recovery archive member type: {name}"
            )
PY_SAFE_MEMBERS
}

atlas_backup_recovery_extract_private() {
  local archive="$1"
  local destination="$2"

  python3 - "$archive" "$destination" <<'PY_EXTRACT_PRIVATE'
import sys
import tarfile

archive_path, destination = sys.argv[1:]

def private_filter(member: tarfile.TarInfo, _path: str) -> tarfile.TarInfo:
    mode = 0o700 if member.isdir() else 0o600
    return member.replace(
        uid=None,
        gid=None,
        uname=None,
        gname=None,
        mode=mode,
    )

try:
    with tarfile.open(archive_path, mode="r:gz") as archive:
        archive.extractall(path=destination, filter=private_filter)
except (OSError, tarfile.TarError) as exc:
    raise SystemExit(f"ERROR: unable to stage recovery archive: {exc}")
PY_EXTRACT_PRIVATE
}

atlas_backup_recovery_validate_staged_restore() {
  local root="$1"
  local surface source archive_path requirement kind group policy extra
  local header
  declare -A policy_by_surface=()

  [[ -d "$root" && ! -L "$root" ]] || {
    echo 'ERROR: staged restore root is not a private directory.' >&2
    return 1
  }

  for metadata in RECOVERY_FORMAT RECOVERY_MANIFEST.tsv SHA256SUMS BACKUP_INFO.txt; do
    [[ -f "$root/$metadata" && ! -L "$root/$metadata" ]] || {
      printf 'ERROR: staged restore metadata is unavailable: %s\n' \
        "$metadata" >&2
      return 1
    }
  done

  local recovery_format

  recovery_format="$(<"$root/RECOVERY_FORMAT")"

  [[ "$recovery_format" == '1' ||
     "$recovery_format" == '2' ]] || {
    echo 'ERROR: staged restore recovery format is unsupported.' >&2
    return 1
  }

  header="$(head -n 1 "$root/RECOVERY_MANIFEST.tsv")"
  [[ "$header" == $'surface\tarchive_path\trequirement\tpolicy' ]] || {
    echo 'ERROR: staged restore manifest header is invalid.' >&2
    return 1
  }

  while IFS=$'\t' read -r surface archive_path requirement policy extra; do
    [[ "$surface" == 'surface' ]] && continue
    [[ -n "$surface" ]] || continue
    [[ -z "$extra" ]] || {
      echo 'ERROR: staged restore manifest row has unexpected fields.' >&2
      return 1
    }
    policy_by_surface["$surface"]="$policy"
  done < "$root/RECOVERY_MANIFEST.tsv"

  while IFS=$'\t' read -r \
    surface source archive_path requirement kind group
  do
    policy="${policy_by_surface[$surface]:-}"
    case "$policy" in
      captured)
        [[ ! -L "$root/$archive_path" ]] || {
          printf 'ERROR: staged recovery surface is symbolic: %s\n' \
            "$surface" >&2
          return 1
        }
        if [[ "$kind" == 'file' ]]; then
          [[ -f "$root/$archive_path" ]] || {
            printf 'ERROR: staged recovery file is unavailable: %s\n' \
              "$surface" >&2
            return 1
          }
        else
          [[ -d "$root/$archive_path" ]] || {
            printf 'ERROR: staged recovery directory is unavailable: %s\n' \
              "$surface" >&2
            return 1
          }
        fi
        ;;
      absent-optional)
        [[ "$requirement" == 'optional' && \
           ! -e "$root/$archive_path" && \
           ! -L "$root/$archive_path" ]] || {
          printf 'ERROR: staged optional-absent surface is invalid: %s\n' \
            "$surface" >&2
          return 1
        }
        ;;
      *)
        printf 'ERROR: staged restore policy is invalid: %s\n' \
          "$surface" >&2
        return 1
        ;;
    esac
  done < <(atlas_backup_recovery_surface_rows)

  if find "$root/state" -type l -print -quit | grep -q .; then
    echo 'ERROR: staged recovery state contains a symbolic link.' >&2
    return 1
  fi

  (
    cd "$root" || exit 1
    sha256sum --check --strict SHA256SUMS >/dev/null
  ) || {
    echo 'ERROR: staged recovery checksum verification failed.' >&2
    return 1
  }
  if [[ "$recovery_format" == '2' ]]; then
    atlas_sports_backend_recovery_validate_staged \
      "$root" || return 1
  fi

}

atlas_backup_recovery_stage_archive() {
  local archive="$1"
  local parent="${2:-/tmp}"
  local before after stage source _surface _archive _requirement _kind _group
  local project_root="${ATLAS_PROJECT_DIR:-/opt/project-atlas}"

  [[ -f "$archive" && ! -L "$archive" ]] || {
    echo 'ERROR: staged restore archive is not a regular file.' >&2
    return 1
  }

  [[ "$parent" == /* && -d "$parent" && ! -L "$parent" ]] || {
    echo 'ERROR: staged restore parent must be an absolute real directory.' >&2
    return 1
  }

  before="$(sha256sum -- "$archive" | awk '{print $1}')" || return 1

  atlas_backup_recovery_validate_archive "$archive" || return 1
  atlas_backup_recovery_validate_safe_members "$archive" || return 1

  stage="$(mktemp -d "$parent/project-atlas-restore.XXXXXX")" || return 1
  chmod 0700 "$stage" || {
    rm -rf -- "$stage"
    return 1
  }

  if [[ "$stage" == "$project_root" || "$stage" == "$project_root/"* ]]; then
    rm -rf -- "$stage"
    echo 'ERROR: staged restore overlaps the Atlas project tree.' >&2
    return 1
  fi

  while IFS=$'\t' read -r \
    _surface source _archive _requirement _kind _group
  do
    if [[ "$stage" == "$source" || "$stage" == "$source/"* ]]; then
      rm -rf -- "$stage"
      echo 'ERROR: staged restore overlaps authoritative Atlas state.' >&2
      return 1
    fi
  done < <(atlas_backup_recovery_surface_rows)

  if ! atlas_backup_recovery_extract_private "$archive" "$stage"; then
    rm -rf -- "$stage"
    return 1
  fi

  after="$(sha256sum -- "$archive" | awk '{print $1}')" || {
    rm -rf -- "$stage"
    return 1
  }

  [[ "$before" == "$after" ]] || {
    rm -rf -- "$stage"
    echo 'ERROR: recovery archive changed during staging.' >&2
    return 1
  }

  if ! atlas_backup_recovery_validate_staged_restore "$stage"; then
    rm -rf -- "$stage"
    return 1
  fi

  printf '%s\n' "$stage"
}

# M-023.25.7.1 validated live-destination planning.
#
# Planning remains read-only. It joins the validated archive manifest to the
# canonical recovery registry and rejects destinations that escape the Atlas
# configuration root, traverse symbolic links, or conflict with the declared
# surface kind. Optional-absent state is planned as an explicit removal.

atlas_backup_recovery_validate_restore_destination() {
  local destination="$1"
  local kind="$2"

  : "${ATLAS_CONFIG_ROOT:?ATLAS_CONFIG_ROOT is required}"

  python3 - "$ATLAS_CONFIG_ROOT" "$destination" "$kind" <<'PY_DESTINATION'
import os
import stat
import sys
from pathlib import Path

root_text, destination_text, kind = sys.argv[1:]

if kind not in {"file", "directory"}:
    raise SystemExit("ERROR: restore destination kind is invalid")

root = Path(root_text)
destination = Path(destination_text)

if not root.is_absolute() or not destination.is_absolute():
    raise SystemExit("ERROR: restore destination must be absolute")

try:
    lexical_common = Path(os.path.commonpath((root, destination)))
except ValueError:
    raise SystemExit("ERROR: restore destination is outside Atlas configuration")

if lexical_common != root or destination == root:
    raise SystemExit("ERROR: restore destination is outside Atlas configuration")

current = destination
while True:
    if current.exists() or current.is_symlink():
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode):
            raise SystemExit(
                f"ERROR: restore destination traverses symbolic link: {current}"
            )
    if current == root or current.parent == current:
        break
    current = current.parent

root_resolved = root.resolve(strict=False)
destination_resolved = destination.resolve(strict=False)

try:
    resolved_common = Path(
        os.path.commonpath((root_resolved, destination_resolved))
    )
except ValueError:
    raise SystemExit("ERROR: restore destination is outside Atlas configuration")

if resolved_common != root_resolved or destination_resolved == root_resolved:
    raise SystemExit("ERROR: restore destination is outside Atlas configuration")

if destination.exists():
    if destination.is_symlink():
        raise SystemExit(
            f"ERROR: restore destination is symbolic: {destination}"
        )
    if kind == "file" and not destination.is_file():
        raise SystemExit(
            f"ERROR: restore destination kind mismatch: {destination}"
        )
    if kind == "directory" and not destination.is_dir():
        raise SystemExit(
            f"ERROR: restore destination kind mismatch: {destination}"
        )
PY_DESTINATION
}

atlas_backup_recovery_restore_plan() {
  local root="$1"
  local surface destination archive_path requirement kind group policy extra
  local action staged_path
  local row_count=0
  declare -A policy_by_surface=()

  atlas_backup_recovery_validate_staged_restore "$root" || return 1

  if [[ "$(<"$root/RECOVERY_FORMAT")" == '2' ]]; then
    echo 'ERROR: recovery format 2 contains native Sports backend state; live restore is not implemented.' >&2
    return 1
  fi


  while IFS=$'\t' read -r surface archive_path requirement policy extra; do
    [[ "$surface" == 'surface' ]] && continue
    [[ -n "$surface" ]] || continue
    [[ -z "$extra" ]] || {
      echo 'ERROR: staged restore manifest row has unexpected fields.' >&2
      return 1
    }
    policy_by_surface["$surface"]="$policy"
  done < "$root/RECOVERY_MANIFEST.tsv"

  while IFS=$'\t' read -r \
    surface destination archive_path requirement kind group
  do
    policy="${policy_by_surface[$surface]:-}"
    case "$policy" in
      captured)
        action='replace'
        staged_path="$root/$archive_path"
        ;;
      absent-optional)
        [[ "$requirement" == 'optional' ]] || {
          printf 'ERROR: required restore surface cannot be absent: %s\n' \
            "$surface" >&2
          return 1
        }
        action='remove-if-present'
        staged_path='-'
        ;;
      *)
        printf 'ERROR: invalid restore-plan policy: %s\n' "$surface" >&2
        return 1
        ;;
    esac

    atlas_backup_recovery_validate_restore_destination \
      "$destination" "$kind" || return 1

    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$surface" "$action" "$kind" "$group" "$staged_path" "$destination"
    row_count=$((row_count + 1))
  done < <(atlas_backup_recovery_surface_rows)

  [[ "$row_count" -eq 13 ]] || {
    printf 'ERROR: restore plan expected 13 surfaces, found %s.\n' \
      "$row_count" >&2
    return 1
  }
}

# M-023.25.7.2 bounded state replacement.
#
# These primitives deliberately do not expose live restore through the CLI.
# They operate only on registry-declared destinations, retain displaced state
# until verification is finalized, and can reverse an applied transaction.
# Production orchestration (lock, maintenance, writer quiescing, backup, and
# verification) is layered on top only after this engine is proved in isolation.

atlas_backup_recovery_validate_apply_plan() {
  local plan_file="$1"
  local transaction_root="$2"

  python3 - "$plan_file" "$transaction_root" <<'PY_APPLY_PLAN'
import os
import sys
from pathlib import Path

plan_file = Path(sys.argv[1])
transaction = Path(sys.argv[2]).resolve(strict=False)

rows: list[tuple[str, Path]] = []
for raw in plan_file.read_text(encoding="utf-8").splitlines():
    if not raw:
        continue
    fields = raw.split("\t")
    if len(fields) != 6:
        raise SystemExit("ERROR: restore apply plan row is malformed")
    surface, _action, _kind, _group, _staged, destination_text = fields
    destination = Path(destination_text).resolve(strict=False)
    rows.append((surface, destination))

if len(rows) != 13:
    raise SystemExit("ERROR: restore apply plan must contain 13 surfaces")

for index, (surface, destination) in enumerate(rows):
    if transaction == destination or transaction in destination.parents:
        raise SystemExit(
            f"ERROR: restore transaction overlaps destination: {surface}"
        )
    if destination in transaction.parents:
        raise SystemExit(
            f"ERROR: restore destination contains transaction state: {surface}"
        )
    for other_surface, other in rows[index + 1 :]:
        if destination == other or destination in other.parents or other in destination.parents:
            raise SystemExit(
                "ERROR: restore destinations overlap: "
                f"{surface}, {other_surface}"
            )
PY_APPLY_PLAN
}

atlas_backup_recovery_apply_plan_row() {
  local surface="$1"
  local action="$2"
  local kind="$3"
  local staged_path="$4"
  local destination="$5"
  local transaction_root="$6"
  local backup_path="$transaction_root/live-rollback/$surface"
  local incoming_path="$transaction_root/incoming/$surface"
  local old_present=false

  atlas_backup_recovery_validate_restore_destination \
    "$destination" "$kind" || return 1

  [[ ! -e "$backup_path" && ! -L "$backup_path" &&
     ! -e "$incoming_path" && ! -L "$incoming_path" ]] || {
    printf 'ERROR: restore transaction path already exists: %s\n' \
      "$surface" >&2
    return 1
  }

  mkdir -p "$(dirname "$backup_path")" "$(dirname "$incoming_path")"

  if [[ -e "$destination" || -L "$destination" ]]; then
    mv -- "$destination" "$backup_path" || {
      printf 'ERROR: unable to preserve live recovery surface: %s\n' \
        "$surface" >&2
      return 1
    }
    old_present=true
  fi

  case "$action" in
    replace)
      if ! cp -a -- "$staged_path" "$incoming_path"; then
        [[ "$old_present" == true ]] && mv -- "$backup_path" "$destination" || true
        printf 'ERROR: unable to prepare replacement surface: %s\n' \
          "$surface" >&2
        return 1
      fi

      mkdir -p "$(dirname "$destination")"
      if ! mv -- "$incoming_path" "$destination"; then
        rm -rf -- "$incoming_path"
        if [[ "$old_present" == true ]]; then
          mv -- "$backup_path" "$destination" || {
            printf 'CRITICAL: unable to restore displaced surface: %s\n' \
              "$surface" >&2
            return 1
          }
        fi
        printf 'ERROR: unable to publish replacement surface: %s\n' \
          "$surface" >&2
        return 1
      fi
      ;;
    remove-if-present)
      [[ "$staged_path" == '-' ]] || {
        if [[ -e "$destination" || -L "$destination" ]]; then
          rm -rf -- "$destination"
        fi
        [[ "$old_present" == true ]] && mv -- "$backup_path" "$destination" || true
        echo 'ERROR: optional-absent restore row has staged content.' >&2
        return 1
      }
      ;;
    *)
      if [[ -e "$destination" || -L "$destination" ]]; then
        rm -rf -- "$destination"
      fi
      [[ "$old_present" == true ]] && mv -- "$backup_path" "$destination" || true
      printf 'ERROR: unsupported restore action: %s\n' "$action" >&2
      return 1
      ;;
  esac
}

atlas_backup_recovery_after_surface_apply() {
  # Intentional no-op seam for deterministic mid-transaction failure tests.
  :
}

atlas_backup_recovery_revert_applied_state() {
  local transaction_root="$1"
  local applied="$transaction_root/applied.tsv"
  local surface kind destination backup_path old_present
  local -a rows=()
  local index

  [[ -d "$transaction_root" && ! -L "$transaction_root" && -f "$applied" ]] || {
    echo 'ERROR: restore rollback transaction is unavailable.' >&2
    return 1
  }

  mapfile -t rows < "$applied"

  for ((index = ${#rows[@]} - 1; index >= 0; index--)); do
    IFS=$'\t' read -r \
      surface kind destination backup_path old_present \
      <<< "${rows[$index]}"

    atlas_backup_recovery_validate_restore_destination \
      "$destination" "$kind" || return 1

    case "$kind" in
      file)
        [[ ! -e "$destination" && ! -L "$destination" ]] || \
          rm -f -- "$destination" || return 1
        ;;
      directory)
        [[ ! -e "$destination" && ! -L "$destination" ]] || \
          rm -rf -- "$destination" || return 1
        ;;
      *)
        return 1
        ;;
    esac

    if [[ "$old_present" == 'true' ]]; then
      [[ -e "$backup_path" && ! -L "$backup_path" ]] || {
        printf 'CRITICAL: preserved restore surface is unavailable: %s\n' \
          "$surface" >&2
        return 1
      }
      mkdir -p "$(dirname "$destination")"
      mv -- "$backup_path" "$destination" || return 1
    fi
  done

  printf '%s\n' 'reverted' > "$transaction_root/status"
}

atlas_backup_recovery_apply_staged_state() {
  local root="$1"
  local transaction_root="$2"
  local plan plan_file applied
  local surface action kind group staged_path destination
  local backup_path old_present
  local index=0

  atlas_backup_recovery_validate_staged_restore "$root" || return 1

  [[ ! -e "$transaction_root" && ! -L "$transaction_root" ]] || {
    echo 'ERROR: restore transaction root already exists.' >&2
    return 1
  }
  atlas_backup_recovery_validate_restore_destination \
    "$transaction_root" directory || return 1

  mkdir -p "$transaction_root/live-rollback" "$transaction_root/incoming"
  chmod 0700 \
    "$transaction_root" \
    "$transaction_root/live-rollback" \
    "$transaction_root/incoming"

  plan="$(atlas_backup_recovery_restore_plan "$root")" || {
    echo 'ERROR: unable to resolve restore application plan.' >&2
    return 1
  }

  plan_file="$transaction_root/plan.tsv"
  applied="$transaction_root/applied.tsv"
  printf '%s\n' "$plan" > "$plan_file"
  : > "$applied"
  chmod 0600 "$plan_file" "$applied"

  atlas_backup_recovery_validate_apply_plan \
    "$plan_file" "$transaction_root" || return 1

  while IFS=$'\t' read -r \
    surface action kind group staged_path destination
  do
    index=$((index + 1))
    backup_path="$transaction_root/live-rollback/$surface"
    if [[ -e "$destination" && ! -L "$destination" ]]; then
      old_present=true
    else
      old_present=false
    fi

    if ! atlas_backup_recovery_apply_plan_row \
      "$surface" "$action" "$kind" "$staged_path" \
      "$destination" "$transaction_root"
    then
      atlas_backup_recovery_revert_applied_state "$transaction_root" || {
        echo 'CRITICAL: restore application failed and automatic revert was incomplete.' >&2
      }
      return 1
    fi

    printf '%s\t%s\t%s\t%s\t%s\n' \
      "$surface" "$kind" "$destination" "$backup_path" "$old_present" \
      >> "$applied"

    if ! atlas_backup_recovery_after_surface_apply "$surface" "$index"; then
      printf 'ERROR: restore application interrupted after surface: %s\n' \
        "$surface" >&2
      atlas_backup_recovery_revert_applied_state "$transaction_root" || {
        echo 'CRITICAL: restore interruption revert was incomplete.' >&2
      }
      return 1
    fi
  done <<< "$plan"

  [[ "$index" -eq 13 ]] || {
    echo 'ERROR: restore application did not apply all declared surfaces.' >&2
    atlas_backup_recovery_revert_applied_state "$transaction_root" || true
    return 1
  }

  rm -rf -- "$transaction_root/incoming"
  printf '%s\n' 'applied-awaiting-verification' > "$transaction_root/status"
}

atlas_backup_recovery_finalize_applied_state() {
  local transaction_root="$1"
  local status

  atlas_backup_recovery_validate_restore_destination \
    "$transaction_root" directory || return 1

  [[ -f "$transaction_root/status" ]] || return 1
  status="$(<"$transaction_root/status")"
  [[ "$status" == 'applied-awaiting-verification' ]] || {
    printf 'ERROR: restore transaction is not finalizable: %s\n' "$status" >&2
    return 1
  }

  rm -rf -- "$transaction_root/live-rollback" "$transaction_root/incoming"
  printf '%s\n' 'verified' > "$transaction_root/status"
}

# M-023.25.6 consumer-level staged-state validation.

atlas_backup_recovery_staged_state_digest() {
  local root="$1"

  python3 - "$root" <<'PY_STAGED_DIGEST'
import hashlib
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1]) / "state"
if not root.is_dir() or root.is_symlink():
    raise SystemExit("ERROR: staged state directory is unavailable")

digest = hashlib.sha256()
for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
    relative = path.relative_to(root).as_posix()
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise SystemExit(f"ERROR: staged state contains symbolic link: {relative}")
    if stat.S_ISDIR(info.st_mode):
        row = f"directory\t{relative}\t{stat.S_IMODE(info.st_mode):o}\n".encode()
        digest.update(row)
        continue
    if stat.S_ISREG(info.st_mode):
        row = f"file\t{relative}\t{stat.S_IMODE(info.st_mode):o}\t{info.st_size}\t".encode()
        digest.update(row)
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"\n")
        continue
    raise SystemExit(f"ERROR: unsupported staged state entry: {relative}")
print(digest.hexdigest())
PY_STAGED_DIGEST
}

atlas_backup_recovery_validate_staged_consumers() {
  local root="$1"
  local project_root="${ATLAS_PROJECT_DIR:-/opt/project-atlas}"
  local validator

  validator="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/validate-recovery-state.py"
  [[ -f "$validator" && ! -L "$validator" ]] || {
    echo 'ERROR: staged recovery consumer validator is unavailable.' >&2
    return 1
  }

  python3 "$validator" "$root" "$project_root"
}
