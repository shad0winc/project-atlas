#!/usr/bin/env bash

source "$(dirname "${BASH_SOURCE[0]}")/../lib/execution-exclusion.sh"

atlas_deployment_root() {
  printf '%s\n' "${ATLAS_DEPLOYMENT_DIR:-$ATLAS_RUNTIME_CONFIG_DIR/deployments}"
}

atlas_deployment_records_dir() {
  printf '%s/records\n' "$(atlas_deployment_root)"
}

atlas_deployment_current_file() {
  printf '%s/current\n' "$(atlas_deployment_root)"
}

atlas_deployment_lock_dir() {
  printf '%s/update.lock\n' "$(atlas_deployment_root)"
}

atlas_deployment_valid_id() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]
}

atlas_deployment_record_dir() {
  local identifier="$1"
  atlas_deployment_valid_id "$identifier" || return 1
  printf '%s/%s\n' "$(atlas_deployment_records_dir)" "$identifier"
}

atlas_deployment_create_recovery_dir() {
  local transaction="$1"
  local surface="$2"
  local records
  local records_real
  local transaction_real
  local transaction_id

  case "$surface" in
    core|ingress|sports)
      ;;
    *)
      printf \
        'ERROR: unsupported rollback recovery surface: %s\n' \
        "$surface" >&2
      return 1
      ;;
  esac

  [[ -d "$transaction" ]] || {
    printf \
      'ERROR: rollback transaction directory is missing: %s\n' \
      "$transaction" >&2
    return 1
  }

  records="$(atlas_deployment_records_dir)"

  [[ -d "$records" ]] || {
    printf \
      'ERROR: deployment records directory is missing: %s\n' \
      "$records" >&2
    return 1
  }

  records_real="$(realpath -e "$records")" || return 1
  transaction_real="$(realpath -e "$transaction")" || return 1

  [[ "$(dirname "$transaction_real")" == "$records_real" ]] || {
    printf \
      'ERROR: rollback transaction is outside the deployment records namespace: %s\n' \
      "$transaction_real" >&2
    return 1
  }

  transaction_id="$(basename "$transaction_real")"

  atlas_deployment_valid_id "$transaction_id" || {
    printf \
      'ERROR: invalid rollback transaction identity: %s\n' \
      "$transaction_id" >&2
    return 1
  }

  mktemp -d \
    "$transaction_real/recovery-${surface}.XXXXXX"
}

atlas_deployment_record_value() {
  local record="$1"
  local key="$2"
  awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' \
    "$record/metadata"
}

atlas_deployment_set_status() {
  local record="$1"
  local status="$2"
  local temporary
  temporary="$(mktemp "$record/.status.XXXXXX")"
  printf '%s\n' "$status" > "$temporary"
  mv -f -- "$temporary" "$record/status"
}

atlas_deployment_runtime_source_root() {
  printf '%s\n' \
    "${ATLAS_RUNTIME_CONFIG_DIR:-/mnt/storage/configs/atlas/runtime}/source"
}

atlas_deployment_runtime_source_generations_dir() {
  printf '%s/generations\n' \
    "$(atlas_deployment_runtime_source_root)"
}

atlas_deployment_runtime_source_generation_dir() {
  local identifier="$1"

  atlas_deployment_valid_id "$identifier" || return 1

  printf '%s/%s\n' \
    "$(atlas_deployment_runtime_source_generations_dir)" \
    "$identifier"
}

atlas_deployment_publish_runtime_source() {
  local identifier="$1"
  local record
  local archive
  local root
  local generations
  local generation
  local temporary
  local archive_sha
  local existing_sha
  local env_source

  atlas_deployment_valid_id "$identifier" || {
    echo 'ERROR: invalid runtime-source deployment identifier.' >&2
    return 1
  }

  record="$(atlas_deployment_record_dir "$identifier")" || return 1

  [[ -d "$record" && -f "$record/status" ]] || {
    printf \
      'ERROR: runtime-source deployment record is unavailable: %s\n' \
      "$identifier" >&2
    return 1
  }

  [[ "$(<"$record/status")" == 'verified' ]] || {
    printf \
      'ERROR: runtime source requires a verified deployment record: %s\n' \
      "$identifier" >&2
    return 1
  }

  archive="$record/core-source.tar.gz"

  [[ -s "$archive" ]] || {
    printf \
      'ERROR: runtime-source archive is unavailable: %s\n' \
      "$archive" >&2
    return 1
  }

  root="$(atlas_deployment_runtime_source_root)"
  generations="$(atlas_deployment_runtime_source_generations_dir)"
  generation="$(atlas_deployment_runtime_source_generation_dir "$identifier")"

  if [[ -e "$root" || -L "$root" ]]; then
    [[ -d "$root" && ! -L "$root" ]] || {
      echo 'ERROR: runtime-source root must be a regular directory.' >&2
      return 1
    }
  else
    mkdir -p "$root" || return 1
  fi

  if [[ -e "$generations" || -L "$generations" ]]; then
    [[ -d "$generations" && ! -L "$generations" ]] || {
      echo 'ERROR: runtime-source generations must be a regular directory.' >&2
      return 1
    }
  else
    mkdir "$generations" || return 1
  fi

  archive_sha="$(sha256sum "$archive" | awk '{print $1}')"

  if [[ -e "$generation" || -L "$generation" ]]; then
    [[ -d "$generation" && ! -L "$generation" ]] || {
      printf \
        'ERROR: runtime-source generation is not a regular directory: %s\n' \
        "$generation" >&2
      return 1
    }

    [[ -f "$generation/.atlas-source-sha256" ]] || {
      printf \
        'ERROR: existing runtime-source generation lacks provenance: %s\n' \
        "$generation" >&2
      return 1
    }

    IFS= read -r existing_sha < "$generation/.atlas-source-sha256"

    [[ "$existing_sha" == "$archive_sha" ]] || {
      printf \
        'ERROR: existing runtime-source generation archive identity differs: %s\n' \
        "$identifier" >&2
      return 1
    }

    [[ -x "$generation/scripts/atlas" ]] || {
      printf \
        'ERROR: existing runtime-source generation lacks executable Atlas CLI: %s\n' \
        "$identifier" >&2
      return 1
    }

    return 0
  fi

  temporary="$(
    mktemp -d \
      "$generations/.${identifier}.XXXXXX"
  )" || return 1

  if ! python3 - "$archive" "$temporary" <<'PYEXTRACT'
from pathlib import PurePosixPath
import sys
import tarfile


archive_path = sys.argv[1]
destination = sys.argv[2]

try:
    archive = tarfile.open(
        archive_path,
        mode="r:gz",
    )
except (OSError, tarfile.TarError) as exc:
    raise SystemExit(
        f"ERROR: unable to inspect runtime-source archive: {exc}"
    )

with archive:
    members = archive.getmembers()
    seen = set()

    for member in members:
        name = member.name
        path = PurePosixPath(name)

        if (
            not name
            or path.is_absolute()
            or ".." in path.parts
            or name.startswith("/")
        ):
            raise SystemExit(
                "ERROR: unsafe runtime-source archive member path: "
                + repr(name)
            )

        if name in seen:
            raise SystemExit(
                "ERROR: duplicate runtime-source archive member: "
                + name
            )

        seen.add(name)

        if member.issym() or member.islnk():
            raise SystemExit(
                "ERROR: runtime-source archive links are not allowed: "
                + name
            )

        if not (member.isfile() or member.isdir()):
            raise SystemExit(
                "ERROR: unsupported runtime-source archive member type: "
                + name
            )

    try:
        archive.extractall(
            path=destination,
            members=members,
            filter="data",
        )
    except (
        OSError,
        tarfile.TarError,
        ValueError,
    ) as exc:
        raise SystemExit(
            f"ERROR: unable to safely extract runtime-source archive: {exc}"
        )
PYEXTRACT
  then
    chmod -R u+w "$temporary" 2>/dev/null || true
    rm -rf -- "$temporary"
    echo 'ERROR: unable to extract runtime-source archive.' >&2
    return 1
  fi

  for required in \
    VERSION \
    scripts/atlas \
    scripts/commands/scheduler.sh \
    atlas/scheduler.py \
    atlas/scheduler_cli.py
  do
    [[ -f "$temporary/$required" ]] || {
      printf \
        'ERROR: runtime-source archive is missing required path: %s\n' \
        "$required" >&2
      rm -rf -- "$temporary"
      return 1
    }
  done

  [[ -x "$temporary/scripts/atlas" ]] || {
    echo 'ERROR: runtime-source Atlas CLI is not executable.' >&2
    rm -rf -- "$temporary"
    return 1
  }

  if [[ -e "$temporary/.env" || -L "$temporary/.env" ]]; then
    echo 'ERROR: runtime-source archive unexpectedly contains .env.' >&2
    rm -rf -- "$temporary"
    return 1
  fi

  env_source="$ATLAS_PROJECT_DIR/.env"

  if [[ -f "$env_source" && ! -L "$env_source" ]]; then
    ln -s -- "$env_source" "$temporary/.env" || {
      rm -rf -- "$temporary"
      return 1
    }
  fi

  printf '%s\n' "$identifier" \
    > "$temporary/.atlas-deployment-id"

  printf '%s\n' "$archive_sha" \
    > "$temporary/.atlas-source-sha256"

  chmod -R a-w "$temporary"

  if ! mv -- "$temporary" "$generation"; then
    chmod -R u+w "$temporary" 2>/dev/null || true
    rm -rf -- "$temporary"
    return 1
  fi

  python3 - "$generations" <<'PYFSYNC'
import os
import sys

directory = sys.argv[1]
flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
descriptor = os.open(directory, flags)

try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
PYFSYNC
}

atlas_deployment_set_current() {
  local identifier="$1"
  local root
  local temporary

  atlas_deployment_valid_id "$identifier" || return 1

  # A deployment may become authoritative only after its immutable
  # scheduler/runtime source generation is present and provenance-verified.
  # The deployment current file remains the single authoritative pointer;
  # systemd derives the executable generation from this deployment identity.
  atlas_deployment_publish_runtime_source "$identifier" || return 1

  root="$(atlas_deployment_root)"
  mkdir -p "$root"
  temporary="$(mktemp "$root/.current.XXXXXX")"
  printf '%s\n' "$identifier" > "$temporary"
  mv -f -- "$temporary" "$(atlas_deployment_current_file)"
}

atlas_deployment_current_id() {
  local file
  local identifier
  file="$(atlas_deployment_current_file)"
  [[ -f "$file" ]] || return 1
  IFS= read -r identifier < "$file"
  atlas_deployment_valid_id "$identifier" || return 1
  printf '%s\n' "$identifier"
}

atlas_deployment_validate_source() {
  local branch
  local head
  local origin_main

  branch="$(git -C "$ATLAS_PROJECT_DIR" branch --show-current)" || return 1
  [[ "$branch" == 'main' ]] || {
    printf 'ERROR: production deployments require main; current branch is %s.\n' \
      "${branch:-detached}" >&2
    return 1
  }

  [[ -z "$(git -C "$ATLAS_PROJECT_DIR" status --porcelain)" ]] || {
    echo 'ERROR: production deployment requires a clean working tree.' >&2
    return 1
  }

  head="$(git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD)" || return 1
  origin_main="$(git -C "$ATLAS_PROJECT_DIR" rev-parse origin/main)" || return 1
  [[ "$head" == "$origin_main" ]] || {
    echo 'ERROR: local main must exactly match origin/main before deployment.' >&2
    return 1
  }
}

atlas_deployment_acquire_lock() {
  local identifier="$1"
  local lock

  atlas_deployment_valid_id "$identifier" || return 1
  lock="$(atlas_deployment_lock_dir)"
  mkdir -p "$(dirname "$lock")"

  if ! mkdir "$lock" 2>/dev/null; then
    printf 'ERROR: deployment lock already exists: %s\n' "$lock" >&2
    return 1
  fi

  {
    printf 'deployment_id=%s\n' "$identifier"
    printf 'pid=%s\n' "$$"
    printf 'started_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$lock/owner"
}

atlas_deployment_lock_matches() {
  local identifier="$1"
  local owner="$(atlas_deployment_lock_dir)/owner"
  [[ -f "$owner" ]] || return 1
  grep -Fxq -- "deployment_id=$identifier" "$owner"
}

atlas_deployment_release_lock() {
  local identifier="$1"
  local lock
  lock="$(atlas_deployment_lock_dir)"
  atlas_deployment_lock_matches "$identifier" || {
    echo 'ERROR: refusing to release a deployment lock owned by another operation.' >&2
    return 1
  }
  rm -f -- "$lock/owner"
  rmdir -- "$lock"
}

atlas_deployment_archive_source() {
  local commit="$1"
  local output="$2"
  local temporary="${output}.partial"

  git -C "$ATLAS_PROJECT_DIR" archive \
    --format=tar.gz \
    --output="$temporary" \
    "$commit" || return 1

  tar -tzf "$temporary" >/dev/null 2>&1 || {
    rm -f -- "$temporary"
    return 1
  }

  mv -f -- "$temporary" "$output"
}

atlas_deployment_capture_images() {
  local record="$1"
  local output="$record/images.tsv"
  local temporary="$record/.images.tsv.partial"
  local surface
  local compose_relative
  local compose_file
  local identifiers
  local container
  local details
  local sports_commit
  local notifications_commit
  local notifications_row
  local notifications_actual_image
  local notifications_surface
  local notifications_compose
  local notifications_project
  local notifications_service
  local notifications_container
  local notifications_reference
  local notifications_image
  local -a notifications_rows=()
  local module_env="$ATLAS_PROJECT_DIR/modules/sports/.env"

  : > "$temporary"

  while IFS='|' read -r surface compose_relative; do
    compose_file="$ATLAS_PROJECT_DIR/$compose_relative"

    [[ -f "$compose_file" ]] || return 1

    identifiers="$(
      docker compose \
        --env-file "$ATLAS_PROJECT_DIR/.env" \
        -f "$compose_file" \
        ps -q
    )" || return 1

    [[ -n "${identifiers//[[:space:]]/}" ]] || return 1

    while IFS= read -r container; do
      [[ -n "$container" ]] || continue

      details="$(
        docker inspect \
          --format \
          '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.Name}}|{{.Config.Image}}|{{.Image}}' \
          "$container"
      )" || return 1

      printf '%s|%s|%s\n' \
        "$surface" \
        "$compose_relative" \
        "$details" \
        >> "$temporary"
    done <<< "$identifiers"
  done <<'SURFACES'
core|docker-compose.yml
ingress|stack/ingress.yml
SURFACES

  sports_commit="$(
    atlas_deployment_record_value \
      "$record" \
      sports_commit
  )"

  if [[ -n "$sports_commit" ]]; then
    compose_relative='modules/sports/docker-compose.yml'
    compose_file="$ATLAS_PROJECT_DIR/$compose_relative"

    [[ -f "$compose_file" ]] || return 1

    [[ -f "$module_env" ]] || {
      echo \
        'ERROR: Sports module environment is unavailable.' \
        >&2
      return 1
    }

    identifiers="$(
      docker compose \
        --env-file "$ATLAS_PROJECT_DIR/.env" \
        --env-file "$ATLAS_PROJECT_DIR/modules/sports/.env" \
        --project-name sports \
        -f "$compose_file" \
        ps -q
    )" || return 1

    [[ -n "${identifiers//[[:space:]]/}" ]] || {
      echo \
        'ERROR: Sports deployment surface has no running containers.' \
        >&2
      return 1
    }

    while IFS= read -r container; do
      [[ -n "$container" ]] || continue

      details="$(
        docker inspect \
          --format \
          '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{.Name}}|{{.Config.Image}}|{{.Image}}' \
          "$container"
      )" || return 1

      printf \
        'sports|modules/sports/docker-compose.yml|%s\n' \
        "$details" \
        >> "$temporary"
    done <<< "$identifiers"
  fi

  notifications_commit="$(
    atlas_deployment_record_value \
      "$record" \
      notifications_commit
  )" || return 1

  if [[ -n "$notifications_commit" ]]; then
    [[ "$notifications_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'ERROR: recorded Notifications commit is invalid.' >&2
      return 1
    }

    [[ -s "$record/notifications-source.tar.gz" ]] &&
      [[ -s "$record/notifications-image.tsv" ]] &&
      [[ -s "$record/notifications-source-commit" ]] || {
        echo 'ERROR: Notifications recovery evidence is missing.' >&2
        return 1
      }

    [[ "$(<"$record/notifications-source-commit")" == \
      "$notifications_commit" ]] || {
        echo 'ERROR: Notifications source provenance differs.' >&2
        return 1
      }

    mapfile -t notifications_rows \
      < "$record/notifications-image.tsv" || return 1

    [[ "${#notifications_rows[@]}" -eq 1 ]] || {
      echo 'ERROR: Notifications image evidence must contain one row.' >&2
      return 1
    }

    notifications_row="${notifications_rows[0]}"

    IFS='|' read -r \
      notifications_surface \
      notifications_compose \
      notifications_project \
      notifications_service \
      notifications_container \
      notifications_reference \
      notifications_image <<< "$notifications_row"

    [[ "$notifications_surface" == notifications &&
      "$notifications_compose" == modules/notifications/docker-compose.yml &&
      "$notifications_project" == notifications &&
      "$notifications_service" == atlas-notifications-worker &&
      "$notifications_container" == /atlas-notifications-worker &&
      -n "$notifications_reference" &&
      "$notifications_reference" != *'|'* &&
      "$notifications_image" =~ ^sha256:[0-9a-f]{64}$ ]] || {
        echo 'ERROR: recorded Notifications image row is invalid.' >&2
        return 1
      }

    notifications_actual_image="$(
      docker inspect \
        --format '{{.Image}}' \
        atlas-notifications-worker
    )" || return 1

    [[ "$notifications_actual_image" == "$notifications_image" ]] || {
      echo 'ERROR: Notifications worker image differs from adoption evidence.' >&2
      return 1
    }

    printf '%s\n' "$notifications_row" >> "$temporary"
  fi

  [[ -s "$temporary" ]] || return 1

  mv -f -- \
    "$temporary" \
    "$output"
}

atlas_deployment_verify_runtime() {
  local record="$1"
  local surface
  local compose_relative
  local project
  local service
  local container_name
  local image_reference
  local expected_image
  local actual_image
  local notifications_commit
  local notifications_expected_row
  local notifications_live_row
  local -a notifications_rows=()

  [[ -s "$record/images.tsv" ]] || return 1

  while IFS='|' read -r \
    surface compose_relative project service container_name image_reference expected_image
  do
    [[ -n "$container_name" && -n "$expected_image" ]] || return 1
    actual_image="$(docker inspect --format '{{.Image}}' "$container_name")" || return 1
    [[ "$actual_image" == "$expected_image" ]] || {
      printf 'ERROR: runtime drift detected for %s (%s).\n' \
        "$service" "$container_name" >&2
      return 1
    }
  done < "$record/images.tsv"

  notifications_commit="$(
    atlas_deployment_record_value \
      "$record" \
      notifications_commit
  )" || return 1

  if [[ -n "$notifications_commit" ]]; then
    [[ "$notifications_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'ERROR: recorded Notifications source commit is invalid.' >&2
      return 1
    }

    [[ -s "$record/notifications-source.tar.gz" ]] &&
      [[ -s "$record/notifications-image.tsv" ]] &&
      [[ -s "$record/notifications-source-commit" ]] || {
        echo 'ERROR: Notifications recovery evidence is missing.' >&2
        return 1
      }

    [[ "$(<"$record/notifications-source-commit")" == \
      "$notifications_commit" ]] || {
        echo 'ERROR: Notifications recovery source commit mismatch.' >&2
        return 1
      }

    mapfile -t notifications_rows \
      < "$record/notifications-image.tsv" || return 1

    [[ "${#notifications_rows[@]}" -eq 1 ]] || {
      echo 'ERROR: Notifications image evidence must contain one row.' >&2
      return 1
    }

    notifications_expected_row="${notifications_rows[0]}"

    [[ "$notifications_expected_row" == \
      'notifications|modules/notifications/docker-compose.yml|notifications|atlas-notifications-worker|/atlas-notifications-worker|'* ]] || {
        echo 'ERROR: Notifications image evidence identity is invalid.' >&2
        return 1
      }

    [[ "$(grep -c '^notifications|' "$record/images.tsv")" -eq 1 ]] &&
      [[ "$(grep -Fxc -- \
        "$notifications_expected_row" \
        "$record/images.tsv")" -eq 1 ]] || {
        echo 'ERROR: Notifications image evidence differs from manifest.' >&2
        return 1
      }

    # Current adoption contract only. An immutable managed Notifications
    # generation needs an explicit recorded source-location contract.
    notifications_live_row="$(
      atlas_deployment_notifications_live_worker_row \
        /opt/project-atlas \
        "$notifications_commit"
    )" || {
      echo 'ERROR: Notifications source or worker attestation failed.' >&2
      return 1
    }

    [[ "$notifications_live_row" == "$notifications_expected_row" ]] || {
      echo 'ERROR: Notifications worker differs from recorded evidence.' >&2
      return 1
    }
  fi
}

# Attest the worker currently executing a specific clean source checkout.
# The single output row follows the seven-field deployment image manifest.
# This function only inspects Git and Docker; it does not adopt or mutate
# any deployment record, image, container, or source directory.
atlas_deployment_notifications_live_worker_row() (
  set -euo pipefail

  local checkout="${1:-}"
  local expected_commit="${2:-}"
  local checkout_real
  local git_root
  local current_commit
  local status

  [[ -n "$checkout" && "$expected_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo 'ERROR: Notifications source checkout and commit are required.' >&2
    return 1
  }

  [[ -d "$checkout" && ! -L "$checkout" ]] || {
    echo 'ERROR: Notifications source checkout is unavailable.' >&2
    return 1
  }

  checkout_real="$(realpath -e -- "$checkout")" || return 1
  git_root="$(git -C "$checkout_real" rev-parse --show-toplevel)" || return 1

  [[ "$(realpath -e -- "$git_root")" == "$checkout_real" ]] || {
    echo 'ERROR: Notifications source must be a Git checkout root.' >&2
    return 1
  }

  current_commit="$(git -C "$checkout_real" rev-parse HEAD)" || return 1

  [[ "$current_commit" == "$expected_commit" ]] || {
    echo 'ERROR: live Notifications source commit mismatch.' >&2
    return 1
  }

  status="$(
    git -C "$checkout_real" status --porcelain --untracked-files=all
  )" || return 1

  [[ -z "$status" ]] || {
    echo 'ERROR: live Notifications source checkout is dirty.' >&2
    return 1
  }

  docker inspect atlas-notifications-worker |
    python3 -c '
import json
import re
import sys

expected_source = sys.argv[1]

try:
    containers = json.load(sys.stdin)
    if not isinstance(containers, list) or len(containers) != 1:
        raise ValueError("Unexpected worker inspection result")

    container = containers[0]
    state = container["State"]
    health = state["Health"]

    if state["Status"] != "running" or health["Status"] != "healthy":
        raise ValueError("Notifications worker is not running and healthy")

    configuration = container["Config"]
    labels = configuration["Labels"]

    if labels["com.docker.compose.project"] != "notifications":
        raise ValueError("Unexpected Notifications Compose project")

    if labels["com.docker.compose.service"] != "atlas-notifications-worker":
        raise ValueError("Unexpected Notifications Compose service")

    if container["Name"] != "/atlas-notifications-worker":
        raise ValueError("Unexpected Notifications container name")

    image_id = container["Image"]
    if not isinstance(image_id, str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", image_id
    ):
        raise ValueError("Invalid Notifications image identity")

    image_reference = configuration["Image"]
    if not isinstance(image_reference, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._:/@-]*", image_reference
    ):
        raise ValueError("Invalid Notifications image reference")

    mounts = [
        mount for mount in container["Mounts"]
        if mount.get("Destination") == "/opt/project-atlas"
    ]

    if len(mounts) != 1:
        raise ValueError("Missing or ambiguous application source mount")

    mount = mounts[0]
    if (
        mount.get("Type") != "bind"
        or mount.get("Source") != expected_source
        or mount.get("RW") is not False
    ):
        raise ValueError("Notifications application source mount mismatch")

    fields = [
        "notifications",
        "modules/notifications/docker-compose.yml",
        "notifications",
        "atlas-notifications-worker",
        "/atlas-notifications-worker",
        image_reference,
        image_id,
    ]

    print("|".join(fields))

except (KeyError, TypeError, ValueError, AttributeError) as error:
    print(
        "ERROR: Notifications worker attestation failed: " + str(error),
        file=sys.stderr,
    )
    raise SystemExit(1)
' "$checkout_real"
)

# Capture matching historical source and image evidence for an unmanaged
# Notifications worker. This primitive does not acquire the deployment lock,
# adopt a baseline, preserve an image tag, or mutate a running container.
# A future guarded deployment caller must own the transaction lock and must
# verify that the evidence marker and all recovery assets are intact.
atlas_deployment_capture_notifications_adoption_evidence() (
  set -euo pipefail

  local record="${1:-}"
  local checkout="${2:-}"
  local expected_commit="${3:-}"
  local archive
  local manifest
  local provenance
  local staged
  local first_row
  local second_row
  local published_archive=false
  local published_manifest=false
  local published_provenance=false

  [[ -d "$record" && ! -L "$record" ]] || {
    echo 'ERROR: Notifications evidence directory is unavailable.' >&2
    return 1
  }

  [[ -n "$checkout" && "$expected_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo 'ERROR: Notifications evidence requires a checkout and commit.' >&2
    return 1
  }

  archive="$record/notifications-source.tar.gz"
  manifest="$record/notifications-image.tsv"
  provenance="$record/notifications-source-commit"

  [[ ! -e "$archive" && ! -L "$archive" ]] &&
    [[ ! -e "$manifest" && ! -L "$manifest" ]] &&
    [[ ! -e "$provenance" && ! -L "$provenance" ]] || {
      echo 'ERROR: Notifications adoption evidence already exists.' >&2
      return 1
    }

  # Capture only after successful, complete live-source and worker attestation.
  first_row="$(
    atlas_deployment_notifications_live_worker_row \
      "$checkout" "$expected_commit"
  )" || return 1

  [[ "$first_row" == notifications\|modules/notifications/docker-compose.yml\|* ]] || {
    echo 'ERROR: unexpected Notifications image-manifest identity.' >&2
    return 1
  }

  staged="$(mktemp -d "$record/.notifications-evidence.XXXXXX")" || return 1

  # The marker is the final published artifact. Remove only files created by
  # this invocation if any intermediate operation fails.
  cleanup_notifications_evidence() {
    local result="$?"

    if (( result != 0 )); then
      if [[ "$published_provenance" == true ]]; then
        rm -f -- "$provenance"
      fi
      if [[ "$published_manifest" == true ]]; then
        rm -f -- "$manifest"
      fi
      if [[ "$published_archive" == true ]]; then
        rm -f -- "$archive"
      fi
    fi

    rm -rf -- "$staged"
  }
  trap cleanup_notifications_evidence EXIT

  atlas_deployment_archive_notifications_checkout \
    "$checkout" \
    "$expected_commit" \
    "$staged/notifications-source.tar.gz" \
    >/dev/null || return 1

  printf '%s\n' "$first_row" > "$staged/notifications-image.tsv"
  printf '%s\n' "$expected_commit" > "$staged/notifications-source-commit"

  [[ -s "$staged/notifications-source.tar.gz" ]] &&
    [[ -s "$staged/notifications-image.tsv" ]] &&
    [[ -s "$staged/notifications-source-commit" ]] || return 1

  # Re-attest after archiving so changed source, mount, health, or image
  # identity cannot silently produce a mixed historical recovery set.
  second_row="$(
    atlas_deployment_notifications_live_worker_row \
      "$checkout" "$expected_commit"
  )" || return 1

  [[ "$second_row" == "$first_row" ]] || {
    echo 'ERROR: Notifications worker changed during evidence capture.' >&2
    return 1
  }

  # Staging and publication occur within the same destination filesystem.
  # Hard-link creation refuses an existing destination; no prior evidence
  # is overwritten. The commit marker is published last.
  ln -- "$staged/notifications-source.tar.gz" "$archive" || return 1
  published_archive=true

  ln -- "$staged/notifications-image.tsv" "$manifest" || return 1
  published_manifest=true

  ln -- "$staged/notifications-source-commit" "$provenance" || return 1
  published_provenance=true

  printf 'Notifications adoption evidence captured: %s\n' "$expected_commit"
)

# Archive the exact clean checkout used by an unmanaged Notifications worker.
# This is a source-capture primitive, not an adoption or deployment operation.
# The caller must separately attest the live container, its image, its mount,
# and the recovery record before any runtime mutation.
atlas_deployment_archive_notifications_checkout() (
  set -euo pipefail

  local checkout="${1:-}"
  local expected_commit="${2:-}"
  local output="${3:-}"
  local checkout_real
  local git_root
  local current_commit
  local temporary=''

  [[ -n "$checkout" && -n "$expected_commit" && -n "$output" ]] || {
    echo 'ERROR: Notifications checkout, commit, and archive path are required.' >&2
    return 2
  }

  [[ "$expected_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo 'ERROR: invalid historical Notifications source commit.' >&2
    return 1
  }

  [[ -d "$checkout" && ! -L "$checkout" ]] || {
    echo 'ERROR: historical Notifications checkout is unavailable.' >&2
    return 1
  }

  checkout_real="$(realpath -e -- "$checkout")" || return 1
  git_root="$(git -C "$checkout_real" rev-parse --show-toplevel)" || return 1

  [[ "$(realpath -e -- "$git_root")" == "$checkout_real" ]] || {
    echo 'ERROR: Notifications source must be a Git checkout root.' >&2
    return 1
  }

  current_commit="$(git -C "$checkout_real" rev-parse HEAD)" || return 1

  [[ "$current_commit" == "$expected_commit" ]] || {
    echo 'ERROR: historical Notifications checkout commit does not match.' >&2
    return 1
  }

  [[ -z "$(git -C "$checkout_real" status --porcelain --untracked-files=all)" ]] || {
    echo 'ERROR: historical Notifications checkout is dirty.' >&2
    return 1
  }

  [[ ! -e "$output" && ! -L "$output" ]] || {
    echo 'ERROR: historical Notifications archive destination already exists.' >&2
    return 1
  }

  [[ -d "$(dirname -- "$output")" ]] || {
    echo 'ERROR: historical Notifications archive parent is unavailable.' >&2
    return 1
  }

  temporary="$(mktemp "${output}.partial.XXXXXX")" || return 1
  trap '[[ -z "$temporary" ]] || rm -f -- "$temporary"' EXIT

  git -C "$checkout_real" archive \
    --format=tar.gz \
    --output="$temporary" \
    "$expected_commit" || return 1

  tar -tzf "$temporary" >/dev/null 2>&1 || {
    echo 'ERROR: historical Notifications source archive validation failed.' >&2
    return 1
  }

  # Same-directory hard-link creation fails if the destination appeared in
  # the meantime. Never overwrite a prior archive or publish a partial one.
  ln -- "$temporary" "$output" || {
    echo 'ERROR: unable to publish historical Notifications archive exclusively.' >&2
    return 1
  }

  rm -f -- "$temporary"
  temporary=''

  printf 'Historical Notifications source archived: %s\n' "$expected_commit"
)

atlas_deployment_create_source_pair() {
  local record="$1"
  local commit="$2"
  atlas_deployment_archive_source "$commit" "$record/core-source.tar.gz" || return 1
  cp -- "$record/core-source.tar.gz" "$record/ingress-source.tar.gz"
}

atlas_deployment_preserve_rollback_images() {
  local baseline="$1"
  local transaction="$2"
  local output="$transaction/rollback-images.tsv"
  local temporary="$transaction/.rollback-images.tsv.partial"
  local transaction_id
  local image_id
  local recovery_tag
  local index=0

  [[ -s "$baseline/images.tsv" ]] || return 1
  transaction_id="$(basename "$transaction")"
  atlas_deployment_valid_id "$transaction_id" || return 1
  : > "$temporary"

  while IFS='|' read -r _ _ _ _ _ _ image_id; do
    [[ -n "$image_id" ]] || return 1
    index=$((index + 1))
    recovery_tag="atlas-rollback:${transaction_id}-${index}"
    docker image inspect "$image_id" >/dev/null 2>&1 || return 1
    docker image tag "$image_id" "$recovery_tag" || return 1
    [[ "$(docker image inspect --format '{{.Id}}' "$recovery_tag")" == "$image_id" ]] || return 1
    printf '%s|%s\n' "$image_id" "$recovery_tag" >> "$temporary"
  done < "$baseline/images.tsv"

  [[ "$index" -gt 0 && -s "$temporary" ]] || return 1
  mv -f -- "$temporary" "$output"
}

atlas_deployment_require_current_record() {
  local identifier
  local record
  local sports_commit
  local notifications_commit
  local -a notifications_rows

  identifier="$(atlas_deployment_current_id)" || {
    echo \
      'ERROR: no verified production deployment baseline exists.' \
      >&2
    return 1
  }

  record="$(
    atlas_deployment_record_dir "$identifier"
  )" || return 1

  [[ -f "$record/status" ]] || return 1

  [[ "$(<"$record/status")" == 'verified' ]] || {
    echo \
      'ERROR: current deployment baseline is not verified.' \
      >&2
    return 1
  }

  [[ -s "$record/core-source.tar.gz" ]] || return 1
  [[ -s "$record/ingress-source.tar.gz" ]] || return 1
  [[ -s "$record/images.tsv" ]] || return 1

  sports_commit="$(
    atlas_deployment_record_value \
      "$record" \
      sports_commit
  )"

  if [[ -n "$sports_commit" ]]; then
    [[ -s "$record/sports-source.tar.gz" ]] || {
      echo \
        'ERROR: Sports recovery source evidence is unavailable.' \
        >&2
      return 1
    }
  fi

  notifications_commit="$(
    atlas_deployment_record_value \
      "$record" \
      notifications_commit
  )" || return 1

  if [[ -n "$notifications_commit" ]]; then
    [[ -s "$record/notifications-source.tar.gz" ]] || {
      echo 'ERROR: Notifications recovery source is unavailable.' >&2
      return 1
    }

    [[ -s "$record/notifications-image.tsv" ]] || {
      echo 'ERROR: Notifications image evidence is unavailable.' >&2
      return 1
    }

    [[ -s "$record/notifications-source-commit" ]] || {
      echo 'ERROR: Notifications source provenance is unavailable.' >&2
      return 1
    }

    [[ "$(<"$record/notifications-source-commit")" == "$notifications_commit" ]] || {
      echo 'ERROR: Notifications source provenance does not match metadata.' >&2
      return 1
    }

    mapfile -t notifications_rows < "$record/notifications-image.tsv" || return 1

    [[ "${#notifications_rows[@]}" -eq 1 ]] || {
      echo 'ERROR: Notifications image evidence must contain one row.' >&2
      return 1
    }

    [[ "${notifications_rows[0]}" == \
      'notifications|modules/notifications/docker-compose.yml|notifications|atlas-notifications-worker|/atlas-notifications-worker|'* ]] || {
      echo 'ERROR: Notifications image evidence has an invalid identity.' >&2
      return 1
    }

    [[ "$(grep -c '^notifications|' "$record/images.tsv")" -eq 1 ]] || {
      echo 'ERROR: Notifications manifest row is missing or duplicated.' >&2
      return 1
    }

    [[ "$(grep -Fxc -- "${notifications_rows[0]}" "$record/images.tsv")" -eq 1 ]] || {
      echo 'ERROR: Notifications image evidence differs from the manifest.' >&2
      return 1
    }
  fi

  printf '%s\n' "$record"
}

atlas_deployment_new_id() {
  local kind="$1"
  printf '%s-%s-%s\n' "$kind" "$(date -u +%Y%m%dT%H%M%SZ)" "$$"
}

atlas_deployment_baseline() {
  local identifier
  local record
  local commit
  local sports_source=''
  local sports_commit=''

  atlas_deployment_validate_source || return 1

  echo 'Baseline doctor:'
  atlas_command_doctor || return 1

  echo 'Baseline verify:'
  atlas_command_verify || return 1

  echo 'Baseline ingress verification:'
  "$ATLAS_PROJECT_DIR/scripts/verify-ingress.sh" || return 1

  if docker inspect \
    atlas-sports-controller \
    >/dev/null 2>&1
  then
    sports_source="$(
      docker inspect \
        atlas-sports-controller \
        --format \
        '{{range .Mounts}}{{if eq .Destination "/opt/project-atlas"}}{{.Source}}{{end}}{{end}}'
    )" || return 1

    [[ -n "$sports_source" ]] || {
      echo \
        'ERROR: live Sports controller source mount is unavailable.' \
        >&2
      return 1
    }

    [[ -d "$sports_source" ]] || {
      echo \
        'ERROR: live Sports controller source directory is unavailable.' \
        >&2
      return 1
    }

    git -C "$sports_source" \
      rev-parse \
      --is-inside-work-tree \
      >/dev/null 2>&1 || {
        echo \
          'ERROR: live Sports source is not a Git worktree.' \
          >&2
        return 1
      }

    [[ -z "$(
      git -C "$sports_source" status --porcelain
    )" ]] || {
      echo \
        'ERROR: live Sports source worktree is dirty.' \
        >&2
      return 1
    }

    sports_commit="$(
      git -C "$sports_source" rev-parse HEAD
    )" || return 1

    [[ "$sports_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo \
        'ERROR: live Sports source commit is invalid.' \
        >&2
      return 1
    }
  fi

  identifier="$(atlas_deployment_new_id baseline)"

  record="$(
    atlas_deployment_record_dir "$identifier"
  )" || return 1

  mkdir -p "$record"

  commit="$(
    git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD
  )"

  cat > "$record/metadata" <<EOF
type=baseline
deployment_id=$identifier
source_commit=$commit
core_commit=$commit
ingress_commit=$commit
sports_commit=$sports_commit
scope=all
migration=none
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  atlas_deployment_create_source_pair \
    "$record" \
    "$commit" || return 1

  if [[ -n "$sports_commit" ]]; then
    git -C "$sports_source" archive \
      --format=tar.gz \
      --output="$record/sports-source.tar.gz" \
      "$sports_commit" || return 1

    [[ -s "$record/sports-source.tar.gz" ]] || return 1

    tar -tzf \
      "$record/sports-source.tar.gz" \
      >/dev/null 2>&1 || return 1
  fi

  atlas_deployment_capture_images \
    "$record" || return 1

  atlas_deployment_verify_runtime \
    "$record" || return 1

  atlas_deployment_set_status \
    "$record" \
    verified

  atlas_deployment_set_current \
    "$identifier"

  printf \
    'Verified production baseline: %s\n' \
    "$identifier"
}


# Historical-worker adoption only: record and attest the existing,
# unchanged Notifications worker. This transaction does not launch,
# upgrade, relocate, or restore the worker. A managed Notifications
# generation requires a separate source-location, update, and rollback
# contract before any managed-worker deployment is enabled.
#
# Before a record exists, failure releases our own deployment lock. Once a
# record is created, failure preserves both the record and lock for explicit
# reconciliation; the operation must never be blindly rerun.
atlas_deployment_adopt_notifications() {
  local checkout="${1:-}"
  local expected_commit="${2:-}"
  local identifier
  local previous_record
  local previous_id
  local previous_notifications
  local core_commit
  local ingress_commit
  local sports_commit
  local source_commit
  local record
  local first_row
  local final_row
  local archive_name

  [[ -n "$checkout" && "$expected_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo 'ERROR: Notifications adoption requires source checkout and commit.' >&2
    return 2
  }

  identifier="$(atlas_deployment_new_id baseline)" || return 1
  atlas_deployment_acquire_lock "$identifier" || return 1

  previous_record="$(atlas_deployment_require_current_record)" || {
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  previous_id="$(basename -- "$previous_record")"
  previous_notifications="$(
    atlas_deployment_record_value "$previous_record" notifications_commit
  )" || {
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  if [[ -n "$previous_notifications" ]]; then
    echo 'ERROR: Notifications already has deployment recovery evidence.' >&2
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  fi

  atlas_deployment_verify_runtime "$previous_record" || {
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  first_row="$(
    atlas_deployment_notifications_live_worker_row \
      "$checkout" "$expected_commit"
  )" || {
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  [[ "$first_row" == notifications\|modules/notifications/docker-compose.yml\|* ]] || {
    echo 'ERROR: unexpected Notifications worker manifest identity.' >&2
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  record="$(atlas_deployment_record_dir "$identifier")" || {
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  [[ ! -e "$record" && ! -L "$record" ]] || {
    echo 'ERROR: Notifications adoption record already exists.' >&2
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  core_commit="$(
    atlas_deployment_record_value "$previous_record" core_commit
  )" || {
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  ingress_commit="$(
    atlas_deployment_record_value "$previous_record" ingress_commit
  )" || {
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  sports_commit="$(
    atlas_deployment_record_value "$previous_record" sports_commit
  )" || {
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  source_commit="$(
    atlas_deployment_record_value "$previous_record" source_commit
  )" || {
    atlas_deployment_release_lock "$identifier" || return 1
    return 1
  }

  if [[ -z "$source_commit" ]]; then
    source_commit="$(
      atlas_deployment_record_value "$previous_record" target_commit
    )" || {
      atlas_deployment_release_lock "$identifier" || return 1
      return 1
    }
  fi

  if [[ -z "$source_commit" ]]; then
    source_commit="$core_commit"
  fi

  [[ "$core_commit" =~ ^[0-9a-f]{40}$ ]] &&
    [[ "$ingress_commit" =~ ^[0-9a-f]{40}$ ]] &&
    [[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'ERROR: previous deployment source metadata is invalid.' >&2
      atlas_deployment_release_lock "$identifier" || return 1
      return 1
    }

  if [[ -n "$sports_commit" ]]; then
    [[ "$sports_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'ERROR: previous Sports source metadata is invalid.' >&2
      atlas_deployment_release_lock "$identifier" || return 1
      return 1
    }
  fi

  # From this point onward, failures retain the record and deployment lock.
  # No production container mutation occurs during adoption.
  mkdir -- "$record" || return 1

  cat > "$record/metadata" <<EOF
type=baseline
deployment_id=$identifier
previous_baseline=$previous_id
target_commit=$source_commit
source_commit=$source_commit
core_commit=$core_commit
ingress_commit=$ingress_commit
sports_commit=$sports_commit
notifications_commit=$expected_commit
scope=all
migration=none
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  for archive_name in core-source.tar.gz ingress-source.tar.gz; do
    [[ -s "$previous_record/$archive_name" ]] || return 1
    cp -- "$previous_record/$archive_name" "$record/$archive_name" || return 1
    cmp -s -- \
      "$previous_record/$archive_name" \
      "$record/$archive_name" || return 1
    tar -tzf "$record/$archive_name" >/dev/null 2>&1 || return 1
  done

  if [[ -n "$sports_commit" ]]; then
    archive_name='sports-source.tar.gz'
    [[ -s "$previous_record/$archive_name" ]] || return 1
    cp -- "$previous_record/$archive_name" "$record/$archive_name" || return 1
    cmp -s -- \
      "$previous_record/$archive_name" \
      "$record/$archive_name" || return 1
    tar -tzf "$record/$archive_name" >/dev/null 2>&1 || return 1
  fi

  atlas_deployment_capture_notifications_adoption_evidence \
    "$record" "$checkout" "$expected_commit" || return 1

  [[ -s "$previous_record/images.tsv" ]] || return 1
  [[ -s "$record/notifications-image.tsv" ]] || return 1

  cp -- "$previous_record/images.tsv" "$record/images.tsv" || return 1

  # Exactly one new Notifications image row; no duplicate inherited row.
  if grep -q '^notifications|' "$record/images.tsv"; then
    echo 'ERROR: previous image manifest already includes Notifications.' >&2
    return 1
  fi

  [[ "$(<"$record/notifications-image.tsv")" == "$first_row" ]] || {
    echo 'ERROR: Notifications evidence differs from original attestation.' >&2
    return 1
  }

  printf '%s\n' "$first_row" >> "$record/images.tsv"

  # Preserve image identities before the newly adopted record is published.
  atlas_deployment_preserve_rollback_images \
    "$record" "$record" || return 1

  atlas_deployment_verify_runtime "$record" || return 1

  final_row="$(
    atlas_deployment_notifications_live_worker_row \
      "$checkout" "$expected_commit"
  )" || return 1

  [[ "$final_row" == "$first_row" ]] || {
    echo 'ERROR: Notifications worker drifted during adoption.' >&2
    return 1
  }

  [[ "$(<"$record/notifications-source-commit")" == "$expected_commit" ]] || {
    echo 'ERROR: Notifications historical source provenance changed.' >&2
    return 1
  }

  [[ -s "$record/notifications-source.tar.gz" ]] &&
    [[ -s "$record/rollback-images.tsv" ]] || return 1

  atlas_deployment_set_status "$record" verified || return 1
  atlas_deployment_set_current "$identifier" || return 1

  atlas_deployment_release_lock "$identifier" || return 1

  printf 'Verified Notifications adoption baseline: %s\n' "$identifier"
}

# Public entry for the historical, live-mounted Notifications worker.
# The internal adoption transaction owns its durable deployment lock.
# This wrapper must not run from a feature branch or an alternate checkout.
atlas_deployment_adopt_notifications_guarded() {
  local exclusion_fd
  local status
  local canonical_root
  local checkout='/opt/project-atlas'
  local expected_commit

  [[ "$#" -eq 0 ]] || {
    echo 'Usage: atlas deployment adopt-notifications' >&2
    return 2
  }

  canonical_root="$(realpath -e -- "$ATLAS_PROJECT_DIR")" || return 1

  [[ "$canonical_root" == '/opt/project-atlas-v1-main' ]] || {
    echo 'ERROR: Notifications adoption requires the canonical Atlas checkout.' >&2
    return 1
  }

  atlas_deployment_validate_source || return 1

  [[ -d "$checkout" && ! -L "$checkout" ]] || {
    echo 'ERROR: historical Notifications checkout is unavailable.' >&2
    return 1
  }

  expected_commit="$(
    git -C "$checkout" rev-parse HEAD
  )" || return 1

  [[ "$expected_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo 'ERROR: historical Notifications source commit is invalid.' >&2
    return 1
  }

  atlas_execution_exclusion_acquire exclusion_fd || return 1

  if atlas_deployment_adopt_notifications \
    "$checkout" "$expected_commit"
  then
    status=0
  else
    status=$?
  fi

  if ! atlas_execution_exclusion_release "$exclusion_fd"; then
    echo 'CRITICAL: unable to release deployment/Scheduler exclusion lock.' >&2
    [[ "$status" -ne 0 ]] || status=1
  fi

  return "$status"
}

atlas_deployment_adopt_sports() {
  local previous_record
  local previous_id
  local identifier
  local record
  local source_commit
  local core_commit
  local ingress_commit
  local previous_sports_commit
  local sports_source
  local sports_commit

  previous_record="$(
    atlas_deployment_require_current_record
  )" || return 1

  previous_id="$(basename -- "$previous_record")"

  previous_sports_commit="$(
    atlas_deployment_record_value \
      "$previous_record" \
      sports_commit
  )"

  [[ -z "$previous_sports_commit" ]] || {
    echo \
      'ERROR: current deployment already includes Sports recovery evidence.' \
      >&2
    return 1
  }

  core_commit="$(
    atlas_deployment_record_value \
      "$previous_record" \
      core_commit
  )"

  ingress_commit="$(
    atlas_deployment_record_value \
      "$previous_record" \
      ingress_commit
  )"

  source_commit="$(
    atlas_deployment_record_value \
      "$previous_record" \
      source_commit
  )"

  if [[ -z "$source_commit" ]]; then
    source_commit="$(
      atlas_deployment_record_value \
        "$previous_record" \
        target_commit
    )"
  fi

  if [[ -z "$source_commit" ]]; then
    source_commit="$core_commit"
  fi

  [[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo \
      'ERROR: deployed source commit is invalid.' \
      >&2
    return 1
  }

  [[ "$core_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo \
      'ERROR: deployed Core commit is invalid.' \
      >&2
    return 1
  }

  [[ "$ingress_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo \
      'ERROR: deployed Ingress commit is invalid.' \
      >&2
    return 1
  }

  atlas_deployment_verify_runtime \
    "$previous_record" || {
    echo \
      'ERROR: current deployment runtime does not match its verified evidence.' \
      >&2
    return 1
  }

  docker inspect \
    atlas-sports-controller \
    >/dev/null 2>&1 || {
    echo \
      'ERROR: live Sports controller is unavailable.' \
      >&2
    return 1
  }

  sports_source="$(
    docker inspect \
      atlas-sports-controller \
      --format \
      '{{range .Mounts}}{{if eq .Destination "/opt/project-atlas"}}{{.Source}}{{end}}{{end}}'
  )" || return 1

  [[ -n "$sports_source" ]] || {
    echo \
      'ERROR: live Sports controller source mount is unavailable.' \
      >&2
    return 1
  }

  [[ -d "$sports_source" ]] || {
    echo \
      'ERROR: live Sports source directory is unavailable.' \
      >&2
    return 1
  }

  git -C "$sports_source" \
    rev-parse \
    --is-inside-work-tree \
    >/dev/null 2>&1 || {
    echo \
      'ERROR: live Sports source is not a Git worktree.' \
      >&2
    return 1
  }

  [[ -z "$(
    git -C "$sports_source" status --porcelain
  )" ]] || {
    echo \
      'ERROR: live Sports source worktree is dirty.' \
      >&2
    return 1
  }

  sports_commit="$(
    git -C "$sports_source" rev-parse HEAD
  )" || return 1

  [[ "$sports_commit" =~ ^[0-9a-f]{40}$ ]] || {
    echo \
      'ERROR: live Sports source commit is invalid.' \
      >&2
    return 1
  }

  identifier="$(
    atlas_deployment_new_id baseline
  )"

  record="$(
    atlas_deployment_record_dir "$identifier"
  )" || return 1

  mkdir -p "$record"

  cat > "$record/metadata" <<EOF
type=baseline
deployment_id=$identifier
previous_baseline=$previous_id
target_commit=$source_commit
source_commit=$source_commit
core_commit=$core_commit
ingress_commit=$ingress_commit
sports_commit=$sports_commit
scope=all
migration=none
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  cp -- \
    "$previous_record/core-source.tar.gz" \
    "$record/core-source.tar.gz" || return 1

  cp -- \
    "$previous_record/ingress-source.tar.gz" \
    "$record/ingress-source.tar.gz" || return 1

  [[ -s "$record/core-source.tar.gz" ]] || return 1
  [[ -s "$record/ingress-source.tar.gz" ]] || return 1

  tar -tzf \
    "$record/core-source.tar.gz" \
    >/dev/null 2>&1 || return 1

  tar -tzf \
    "$record/ingress-source.tar.gz" \
    >/dev/null 2>&1 || return 1

  [[ "$(
    sha256sum "$previous_record/core-source.tar.gz" |
      awk '{print $1}'
  )" == "$(
    sha256sum "$record/core-source.tar.gz" |
      awk '{print $1}'
  )" ]] || {
    echo \
      'ERROR: adopted Core source archive identity changed.' \
      >&2
    return 1
  }

  [[ "$(
    sha256sum "$previous_record/ingress-source.tar.gz" |
      awk '{print $1}'
  )" == "$(
    sha256sum "$record/ingress-source.tar.gz" |
      awk '{print $1}'
  )" ]] || {
    echo \
      'ERROR: adopted Ingress source archive identity changed.' \
      >&2
    return 1
  }

  git -C "$sports_source" archive \
    --format=tar.gz \
    --output="$record/sports-source.tar.gz" \
    "$sports_commit" || return 1

  [[ -s "$record/sports-source.tar.gz" ]] || return 1

  tar -tzf \
    "$record/sports-source.tar.gz" \
    >/dev/null 2>&1 || return 1

  atlas_deployment_capture_images \
    "$record" || return 1

  atlas_deployment_verify_runtime \
    "$record" || return 1

  atlas_deployment_set_status \
    "$record" \
    verified

  atlas_deployment_set_current \
    "$identifier" || return 1

  printf \
    'Verified production baseline: %s\n' \
    "$identifier"
}

atlas_deployment_prepare_update() {
  local identifier="$1"
  local scope="$2"
  local previous_record="$3"
  local record
  local target_commit
  local previous_id
  local core_commit
  local ingress_commit
  local sports_commit
  local notifications_commit

  record="$(
    atlas_deployment_record_dir "$identifier"
  )" || return 1

  mkdir -p "$record"

  target_commit="$(
    git -C "$ATLAS_PROJECT_DIR" rev-parse HEAD
  )"

  previous_id="$(basename "$previous_record")"

  core_commit="$(
    atlas_deployment_record_value \
      "$previous_record" \
      core_commit
  )"

  ingress_commit="$(
    atlas_deployment_record_value \
      "$previous_record" \
      ingress_commit
  )"

  sports_commit="$(
    atlas_deployment_record_value \
      "$previous_record" \
      sports_commit
  )"

  notifications_commit="$(
    atlas_deployment_record_value \
      "$previous_record" \
      notifications_commit
  )" || return 1

  case "$scope" in
    core)
      core_commit="$target_commit"
      ;;
    ingress)
      ingress_commit="$target_commit"
      ;;
    all)
      core_commit="$target_commit"
      ingress_commit="$target_commit"

      if [[ -n "$sports_commit" ]]; then
        sports_commit="$target_commit"
      fi
      ;;
  esac

  cat > "$record/metadata" <<EOF
type=update
deployment_id=$identifier
previous_baseline=$previous_id
target_commit=$target_commit
core_commit=$core_commit
ingress_commit=$ingress_commit
sports_commit=$sports_commit
notifications_commit=$notifications_commit
scope=$scope
migration=none
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  cp -- \
    "$previous_record/images.tsv" \
    "$record/pre-images.tsv"

  atlas_deployment_preserve_rollback_images \
    "$previous_record" \
    "$record" || return 1

  if [[ "$scope" == 'core' || "$scope" == 'all' ]]; then
    atlas_deployment_archive_source \
      "$target_commit" \
      "$record/core-source.tar.gz" || return 1
  else
    cp -- \
      "$previous_record/core-source.tar.gz" \
      "$record/core-source.tar.gz"
  fi

  if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]; then
    atlas_deployment_archive_source \
      "$target_commit" \
      "$record/ingress-source.tar.gz" || return 1
  else
    cp -- \
      "$previous_record/ingress-source.tar.gz" \
      "$record/ingress-source.tar.gz"
  fi

  if [[ -n "$sports_commit" ]]; then
    if [[ "$scope" == 'all' ]]; then
      atlas_deployment_archive_source \
        "$target_commit" \
        "$record/sports-source.tar.gz" || return 1
    else
      [[ -s "$previous_record/sports-source.tar.gz" ]] || {
        echo \
          'ERROR: previous Sports source archive is unavailable.' \
          >&2
        return 1
      }

      cp -- \
        "$previous_record/sports-source.tar.gz" \
        "$record/sports-source.tar.gz"
    fi
  fi

  if [[ -n "$notifications_commit" ]]; then
    [[ "$notifications_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'ERROR: previous Notifications commit is invalid.' >&2
      return 1
    }

    local evidence
    for evidence in \
      notifications-source.tar.gz \
      notifications-image.tsv \
      notifications-source-commit
    do
      [[ -s "$previous_record/$evidence" ]] || {
        printf 'ERROR: previous Notifications evidence is missing: %s\n' \
          "$evidence" >&2
        return 1
      }
    done

    [[ "$(<"$previous_record/notifications-source-commit")" == \
      "$notifications_commit" ]] || {
      echo 'ERROR: previous Notifications source provenance differs.' >&2
      return 1
    }

    [[ "$(
      grep -Fxc -- \
        "$(<"$previous_record/notifications-image.tsv")" \
        "$record/pre-images.tsv"
    )" -eq 1 ]] || {
      echo 'ERROR: previous Notifications image evidence differs.' >&2
      return 1
    }

    for evidence in \
      notifications-source.tar.gz \
      notifications-image.tsv \
      notifications-source-commit
    do
      cp -- \
        "$previous_record/$evidence" \
        "$record/$evidence" || return 1

      cmp -s -- \
        "$previous_record/$evidence" \
        "$record/$evidence" || return 1
    done
  fi

  atlas_deployment_set_status \
    "$record" \
    prepared
}

atlas_deployment_record_backup() {
  local identifier="$1"
  local backup_file="$2"
  local record
  record="$(atlas_deployment_record_dir "$identifier")" || return 1
  [[ -f "$backup_file" ]] || return 1
  tar -tzf "$backup_file" >/dev/null 2>&1 || return 1
  printf '%s\n' "$backup_file" > "$record/backup_file"
}

atlas_deployment_complete_update() {
  local identifier="$1"
  local record
  record="$(atlas_deployment_record_dir "$identifier")" || return 1

  # images.tsv is durable post-apply evidence captured before health
  # verification. Finalization verifies that same evidence instead of
  # replacing it with a later observation of the live runtime.
  [[ -s "$record/images.tsv" ]] || return 1
  atlas_deployment_verify_runtime "$record" || return 1
  atlas_deployment_set_status "$record" verified
  atlas_deployment_set_current "$identifier"
}

atlas_deployment_status() {
  local identifier
  local record

  if ! identifier="$(atlas_deployment_current_id)"; then
    echo 'Verified production baseline: none'
    return 0
  fi

  record="$(
    atlas_deployment_record_dir "$identifier"
  )"

  printf \
    'Verified production baseline: %s\n' \
    "$identifier"

  printf \
    'Status: %s\n' \
    "$(<"$record/status")"

  printf \
    'Core source: %s\n' \
    "$(atlas_deployment_record_value "$record" core_commit)"

  printf \
    'Ingress source: %s\n' \
    "$(atlas_deployment_record_value "$record" ingress_commit)"

  printf \
    'Sports source: %s\n' \
    "$(atlas_deployment_record_value "$record" sports_commit)"
}

atlas_deployment_publish_reconciliation_baseline() {
  local failed_identifier="$1"
  local transaction="$2"
  local previous_id="$3"
  local baseline="$4"
  local scope="$5"
  local identifier
  local record
  local temporary
  local source_commit
  local core_commit
  local ingress_commit
  local sports_commit
  local notifications_commit
  local notifications_evidence
  local recovery_source='none'

  identifier="$(
    atlas_deployment_new_id baseline-reconciliation
  )"

  record="$(
    atlas_deployment_record_dir "$identifier"
  )" || return 1

  [[ ! -e "$record" ]] || {
    printf \
      'ERROR: reconciliation baseline already exists: %s\n' \
      "$identifier" >&2
    return 1
  }

  temporary="$(
    mktemp -d \
      "$(atlas_deployment_records_dir)/.${identifier}.XXXXXX"
  )" || return 1

  source_commit="$(
    atlas_deployment_record_value \
      "$baseline" \
      source_commit
  )"

  if [[ -z "$source_commit" ]]; then
    source_commit="$(
      atlas_deployment_record_value \
        "$baseline" \
        target_commit
    )"
  fi

  core_commit="$(
    atlas_deployment_record_value \
      "$baseline" \
      core_commit
  )"

  ingress_commit="$(
    atlas_deployment_record_value \
      "$baseline" \
      ingress_commit
  )"

  sports_commit="$(
    atlas_deployment_record_value \
      "$baseline" \
      sports_commit
  )"

  [[ -n "$source_commit" ]] || {
    echo \
      'ERROR: previous baseline source identity is unavailable.' \
      >&2
    rm -rf -- "$temporary"
    return 1
  }

  [[ -n "$core_commit" && -n "$ingress_commit" ]] || {
    echo \
      'ERROR: previous baseline component identity is unavailable.' \
      >&2
    rm -rf -- "$temporary"
    return 1
  }

  [[ -f "$baseline/core-source.tar.gz" ]] || {
    echo \
      'ERROR: previous baseline core source archive is unavailable.' \
      >&2
    rm -rf -- "$temporary"
    return 1
  }

  [[ -f "$baseline/ingress-source.tar.gz" ]] || {
    echo \
      'ERROR: previous baseline ingress source archive is unavailable.' \
      >&2
    rm -rf -- "$temporary"
    return 1
  }

  if [[ -n "$sports_commit" ]]; then
    [[ -f "$baseline/sports-source.tar.gz" ]] || {
      echo \
        'ERROR: previous baseline Sports source archive is unavailable.' \
        >&2
      rm -rf -- "$temporary"
      return 1
    }
  fi

  notifications_commit="$(
    atlas_deployment_record_value \
      "$baseline" \
      notifications_commit
  )" || {
    rm -rf -- "$temporary"
    return 1
  }

  if [[ -n "$notifications_commit" ]]; then
    [[ "$notifications_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'ERROR: previous Notifications source identity is invalid.' >&2
      rm -rf -- "$temporary"
      return 1
    }

    [[ -s "$baseline/notifications-source.tar.gz" ]] &&
      [[ -s "$baseline/notifications-image.tsv" ]] &&
      [[ -s "$baseline/notifications-source-commit" ]] &&
      [[ -s "$baseline/images.tsv" ]] || {
        echo 'ERROR: previous Notifications recovery evidence is missing.' >&2
        rm -rf -- "$temporary"
        return 1
      }

    [[ "$(<"$baseline/notifications-source-commit")" == \
      "$notifications_commit" ]] || {
        echo 'ERROR: previous Notifications source provenance differs.' >&2
        rm -rf -- "$temporary"
        return 1
      }

    [[ "$(grep -c '^notifications|' "$baseline/images.tsv")" -eq 1 ]] &&
      [[ "$(grep -Fxc -- \
        "$(<"$baseline/notifications-image.tsv")" \
        "$baseline/images.tsv")" -eq 1 ]] || {
        echo 'ERROR: previous Notifications image evidence differs.' >&2
        rm -rf -- "$temporary"
        return 1
      }
  fi

  case "$scope" in
    core)
      ;;
    ingress|all)
      recovery_source="$(
        atlas_deployment_rollback_recovery_source \
          "$transaction" \
          ingress
      )" || {
        rm -rf -- "$temporary"
        return 1
      }
      ;;
    *)
      printf \
        'ERROR: unsupported reconciliation scope: %s\n' \
        "$scope" >&2
      rm -rf -- "$temporary"
      return 1
      ;;
  esac

  cp -- \
    "$baseline/core-source.tar.gz" \
    "$temporary/core-source.tar.gz" || {
      rm -rf -- "$temporary"
      return 1
    }

  cp -- \
    "$baseline/ingress-source.tar.gz" \
    "$temporary/ingress-source.tar.gz" || {
      rm -rf -- "$temporary"
      return 1
    }

  if [[ -n "$sports_commit" ]]; then
    cp -- \
      "$baseline/sports-source.tar.gz" \
      "$temporary/sports-source.tar.gz" || {
        rm -rf -- "$temporary"
        return 1
      }
  fi

  if [[ -n "$notifications_commit" ]]; then
    for notifications_evidence in \
      notifications-source.tar.gz \
      notifications-image.tsv \
      notifications-source-commit
    do
      cp -- \
        "$baseline/$notifications_evidence" \
        "$temporary/$notifications_evidence" || {
          rm -rf -- "$temporary"
          return 1
        }

      cmp -s -- \
        "$baseline/$notifications_evidence" \
        "$temporary/$notifications_evidence" || {
          rm -rf -- "$temporary"
          return 1
        }
    done
  fi

  cat > "$temporary/metadata" <<EOF
type=baseline
deployment_id=$identifier
baseline_kind=rollback-reconciliation
previous_baseline=$previous_id
failed_deployment=$failed_identifier
source_commit=$source_commit
core_commit=$core_commit
ingress_commit=$ingress_commit
sports_commit=$sports_commit
notifications_commit=$notifications_commit
scope=all
migration=none
reason=post-rollback-failure-finalization
source_claim=verified-previous-baseline-plus-observed-runtime
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  cat > "$temporary/provenance" <<EOF
reconciliation_reason=post-rollback-failure-finalization
failed_deployment=$failed_identifier
authoritative_previous_baseline=$previous_id
recovery_scope=$scope
source_commit=$source_commit
core_commit=$core_commit
ingress_commit=$ingress_commit
sports_commit=$sports_commit
notifications_commit=$notifications_commit
historical_recovery_source=$recovery_source
source_claim=verified-previous-baseline-plus-observed-runtime
EOF

  atlas_deployment_capture_images "$temporary" || {
    rm -rf -- "$temporary"
    return 1
  }

  atlas_deployment_verify_runtime "$temporary" || {
    rm -rf -- "$temporary"
    return 1
  }

  atlas_deployment_set_status \
    "$temporary" \
    verified || {
      rm -rf -- "$temporary"
      return 1
    }

  (
    cd "$temporary"

    sha256sum \
      images.tsv \
      status \
      metadata \
      provenance \
      core-source.tar.gz \
      ingress-source.tar.gz \
      > MANIFEST.sha256

    if [[ -f sports-source.tar.gz ]]; then
      sha256sum \
        sports-source.tar.gz \
        >> MANIFEST.sha256
    fi

    if [[ -n "$notifications_commit" ]]; then
      sha256sum \
        notifications-source.tar.gz \
        notifications-image.tsv \
        notifications-source-commit \
        >> MANIFEST.sha256
    fi

    sha256sum \
      -c \
      MANIFEST.sha256 \
      >&2
  ) || {
    rm -rf -- "$temporary"
    return 1
  }

  mv -- \
    "$temporary" \
    "$record" || {
      rm -rf -- "$temporary"
      return 1
    }

  printf '%s\n' "$identifier"
}

atlas_deployment_recover_failed_rollback() {
  local identifier="$1"
  local transaction
  local transaction_type
  local status
  local migration
  local previous_id
  local baseline
  local current_id
  local scope
  local reconciliation_id

  atlas_deployment_valid_id "$identifier" || {
    echo 'ERROR: invalid deployment identifier.' >&2
    return 2
  }

  atlas_deployment_validate_source || return 1

  transaction="$(atlas_deployment_record_dir "$identifier")" || return 1

  [[ -d "$transaction" && -f "$transaction/metadata" && -f "$transaction/status" ]] || {
    printf 'ERROR: deployment record is incomplete: %s\n' "$identifier" >&2
    return 1
  }

  transaction_type="$(atlas_deployment_record_value "$transaction" type)"
  status="$(<"$transaction/status")"

  [[ "$transaction_type" == 'update' && "$status" == 'failed' ]] || {
    printf \
      'ERROR: deployment %s is not failed-rollback recovery eligible (type=%s status=%s).\n' \
      "$identifier" \
      "${transaction_type:-unknown}" \
      "${status:-unknown}" >&2
    return 1
  }

  migration="$(atlas_deployment_record_value "$transaction" migration)"

  [[ "$migration" == 'none' ]] || {
    echo 'ERROR: failed-rollback recovery requires migration=none.' >&2
    return 1
  }

  previous_id="$(
    atlas_deployment_record_value "$transaction" previous_baseline
  )"

  atlas_deployment_valid_id "$previous_id" || {
    echo 'ERROR: failed transaction has an invalid previous baseline identity.' >&2
    return 1
  }

  baseline="$(atlas_deployment_record_dir "$previous_id")" || return 1

  [[ -d "$baseline" && -f "$baseline/status" ]] || {
    echo 'ERROR: previous deployment baseline is unavailable.' >&2
    return 1
  }

  [[ "$(<"$baseline/status")" == 'verified' ]] || {
    echo 'ERROR: previous deployment baseline is not verified.' >&2
    return 1
  }

  current_id="$(atlas_deployment_current_id)" || {
    echo 'ERROR: current deployment baseline cannot be resolved.' >&2
    return 1
  }

  [[ "$current_id" == "$previous_id" ]] || {
    echo 'ERROR: failed deployment no longer points at the current baseline.' >&2
    return 1
  }

  [[ -d "$(atlas_deployment_lock_dir)" ]] || {
    echo 'ERROR: failed-rollback recovery requires the original deployment lock.' >&2
    return 1
  }

  atlas_deployment_lock_matches "$identifier" || {
    echo 'ERROR: another deployment owns the active lock.' >&2
    return 1
  }

  [[ -f "$(atlas_maintenance_flag)" ]] || {
    echo 'ERROR: failed-rollback recovery requires maintenance mode to remain enabled.' >&2
    return 1
  }

  scope="$(atlas_deployment_record_value "$transaction" scope)"

  case "$scope" in
    core)
      ;;
    ingress|all)
      atlas_deployment_rollback_recovery_source \
        "$transaction" \
        ingress \
        >/dev/null || {
          echo 'ERROR: historical rollback recovery source is unavailable.' >&2
          return 1
        }
      ;;
    *)
      printf \
        'ERROR: unsupported failed-rollback recovery scope: %s\n' \
        "$scope" >&2
      return 1
      ;;
  esac

  echo 'Private restored-runtime verification:'

  atlas_deployment_verify_rollback_runtime \
    "$transaction" \
    "$scope" || {
      echo 'ERROR: restored rollback runtime verification failed.' >&2
      return 1
    }

  if ! atlas_command_maintenance disable; then
    echo 'ERROR: unable to reopen public traffic during failed-rollback recovery.' >&2
    return 1
  fi

  echo 'Public restored-runtime verification:'

  atlas_deployment_verify_rollback_runtime \
    "$transaction" \
    "$scope" || {
      atlas_command_maintenance enable || true
      echo 'ERROR: public rollback verification failed; maintenance restored.' >&2
      return 1
    }

  reconciliation_id="$(
    atlas_deployment_publish_reconciliation_baseline \
      "$identifier" \
      "$transaction" \
      "$previous_id" \
      "$baseline" \
      "$scope"
  )" || {
    atlas_command_maintenance enable || true
    echo 'ERROR: unable to publish verified reconciliation baseline; maintenance restored.' >&2
    return 1
  }

  atlas_deployment_set_current "$reconciliation_id" || {
    atlas_command_maintenance enable || true
    echo 'ERROR: unable to publish reconciliation baseline as current; maintenance restored.' >&2
    return 1
  }

  if ! atlas_deployment_release_lock "$identifier"; then
    atlas_command_maintenance enable || true
    echo 'ERROR: unable to release failed deployment lock; maintenance restored.' >&2
    return 1
  fi

  printf \
    'Failed-rollback recovery complete: %s -> %s\n' \
    "$identifier" \
    "$reconciliation_id"
}

atlas_deployment_restore_surface() {
  local baseline="$1"
  local transaction="$2"
  local surface="$3"
  local recovery
  local archive="$baseline/${surface}-source.tar.gz"
  local rollback_images="$transaction/rollback-images.tsv"
  local override
  local row
  local compose_relative
  local project
  local service
  local container_name
  local image_reference
  local image_id
  local recovery_tag
  local restored=0

  [[ -s "$archive" ]] || return 1
  [[ -s "$rollback_images" ]] || {
    echo 'ERROR: rollback image alias evidence is missing.' >&2
    return 1
  }

  recovery="$(
    atlas_deployment_create_recovery_dir       "$transaction"       "$surface"
  )" || return 1

  tar -xzf "$archive" -C "$recovery" || return 1

  if [[ -f "$ATLAS_PROJECT_DIR/.env" && ! -e "$recovery/.env" ]]; then
    ln -s -- "$ATLAS_PROJECT_DIR/.env" "$recovery/.env"
  fi

  if [[ "$surface" == 'sports' ]]; then
    [[ -f "$ATLAS_PROJECT_DIR/modules/sports/.env" ]] || {
      echo \
        'ERROR: external Sports module environment is unavailable.' \
        >&2
      return 1
    }

    mkdir -p \
      "$recovery/modules/sports"

    if [[ ! -e "$recovery/modules/sports/.env" ]]; then
      ln -s -- \
        "$ATLAS_PROJECT_DIR/modules/sports/.env" \
        "$recovery/modules/sports/.env"
    fi
  fi

  override="$recovery/rollback-images.yml"

  printf 'services:\n' > "$override"

  while IFS='|' read -r \
    row compose_relative project service container_name image_reference image_id
  do
    [[ "$row" == "$surface" ]] || continue
    [[ -n "$service" && -n "$image_id" ]] || return 1

    recovery_tag="$(
      awk -F'|' -v expected="$image_id" \
        '$1 == expected {print $2; exit}' \
        "$rollback_images"
    )"

    [[ -n "$recovery_tag" ]] || {
      printf \
        'ERROR: rollback alias missing for image %s (%s).\n' \
        "$image_id" \
        "$service" >&2
      return 1
    }

    docker image inspect "$recovery_tag" >/dev/null 2>&1 || {
      printf \
        'ERROR: rollback alias unavailable: %s\n' \
        "$recovery_tag" >&2
      return 1
    }

    [[ "$(
      docker image inspect \
        --format '{{.Id}}' \
        "$recovery_tag"
    )" == "$image_id" ]] || {
      printf \
        'ERROR: rollback alias identity mismatch: %s\n' \
        "$recovery_tag" >&2
      return 1
    }

    printf '  %s:\n' "$service" >> "$override"
    printf '    image: %s\n' "$recovery_tag" >> "$override"

    restored=$((restored + 1))
  done < "$baseline/images.tsv"

  [[ "$restored" -gt 0 ]] || {
    printf \
      'ERROR: no rollback services found for surface: %s\n' \
      "$surface" >&2
    return 1
  }

  compose_relative="$(
    awk -F'|' \
      -v surface="$surface" \
      '$1 == surface {print $2; exit}' \
      "$baseline/images.tsv"
  )"

  project="$(
    awk -F'|' \
      -v surface="$surface" \
      '$1 == surface {print $3; exit}' \
      "$baseline/images.tsv"
  )"

  [[ -n "$compose_relative" && -n "$project" ]] || return 1

  (
    cd "$recovery"

    if [[ "$surface" == 'sports' ]]; then
      ATLAS_PROJECT_DIR="$recovery" \
        docker compose \
          --env-file "$recovery/.env" \
          --env-file "$recovery/modules/sports/.env" \
          --project-name "$project" \
          -f "$recovery/$compose_relative" \
          -f "$override" \
          up -d --no-build --pull never
    else
      docker compose \
        --env-file "$recovery/.env" \
        --project-name "$project" \
        -f "$recovery/$compose_relative" \
        -f "$override" \
        up -d --no-build --pull never
    fi
  )
}

atlas_deployment_ingress_container_state() {
  local container="$1"
  local status
  local health

  status="$(
    docker inspect \
      --format '{{.State.Status}}' \
      "$container"
  )" || return 1

  health="$(
    docker inspect \
      --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' \
      "$container"
  )" || return 1

  printf '%s|%s\n' "$status" "$health"
}

atlas_deployment_readiness_sleep() {
  sleep "$1"
}

atlas_deployment_wait_for_ingress_readiness() {
  local attempts="${ATLAS_ROLLBACK_READINESS_ATTEMPTS:-18}"
  local interval="${ATLAS_ROLLBACK_READINESS_INTERVAL_SECONDS:-5}"
  local attempt
  local container
  local state
  local status
  local health
  local pending

  [[ "$attempts" =~ ^[1-9][0-9]*$ ]] || {
    printf \
      'ERROR: ATLAS_ROLLBACK_READINESS_ATTEMPTS must be a positive integer: %s\n' \
      "$attempts" >&2
    return 1
  }

  [[ "$interval" =~ ^[0-9]+$ ]] || {
    printf \
      'ERROR: ATLAS_ROLLBACK_READINESS_INTERVAL_SECONDS must be a non-negative integer: %s\n' \
      "$interval" >&2
    return 1
  }

  for ((attempt = 1; attempt <= attempts; attempt++)); do
    pending=0

    for container in \
      atlas-api \
      atlas-portal \
      atlas-caddy
    do
      state="$(
        atlas_deployment_ingress_container_state "$container"
      )" || {
        printf \
          'ERROR: rollback ingress readiness failed: unable to inspect %s\n' \
          "$container" >&2
        return 1
      }

      IFS='|' read -r status health <<<"$state"

      if [[ "$status" != 'running' ]]; then
        printf \
          'ERROR: rollback ingress readiness failed: %s is not running (status=%s health=%s)\n' \
          "$container" \
          "${status:-missing}" \
          "${health:-missing}" >&2
        return 1
      fi

      case "$health" in
        healthy)
          ;;
        starting)
          pending=1
          ;;
        unhealthy|missing|'')
          printf \
            'ERROR: rollback ingress readiness failed: %s health=%s\n' \
            "$container" \
            "${health:-missing}" >&2
          return 1
          ;;
        *)
          printf \
            'ERROR: rollback ingress readiness failed: %s has unexpected health state=%s\n' \
            "$container" \
            "$health" >&2
          return 1
          ;;
      esac
    done

    if [[ "$pending" -eq 0 ]]; then
      return 0
    fi

    if [[ "$attempt" -ge "$attempts" ]]; then
      printf \
        'ERROR: rollback ingress readiness timed out after %s attempts.\n' \
        "$attempts" >&2
      return 1
    fi

    atlas_deployment_readiness_sleep "$interval"
  done

  return 1
}


atlas_deployment_rollback_recovery_source() {
  local transaction="$1"
  local surface="$2"
  local candidate
  local -a candidates=()

  case "$surface" in
    core|ingress|sports)
      ;;
    *)
      printf \
        'ERROR: unsupported rollback recovery source surface: %s\n' \
        "$surface" >&2
      return 1
      ;;
  esac

  [[ -d "$transaction" ]] || {
    printf \
      'ERROR: rollback transaction directory is missing: %s\n' \
      "$transaction" >&2
    return 1
  }

  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    candidates+=("$candidate")
  done < <(
    find "$transaction" \
      -mindepth 1 \
      -maxdepth 1 \
      -type d \
      -name "recovery-${surface}.*" \
      -print |
      LC_ALL=C sort
  )

  [[ "${#candidates[@]}" -eq 1 ]] || {
    printf \
      'ERROR: rollback recovery source is ambiguous for %s: found %s candidates.\n' \
      "$surface" \
      "${#candidates[@]}" >&2
    return 1
  }

  printf '%s\n' "${candidates[0]}"
}

atlas_deployment_verify_rollback_runtime() {
  local transaction="$1"
  local scope="$2"
  local recovery
  local ingress_verifier
  local previous_id
  local baseline
  local notifications_commit

  atlas_command_doctor || return 1

  case "$scope" in
    core)
      atlas_command_verify || return 1
      ;;
    ingress|all)
      recovery="$(
        atlas_deployment_rollback_recovery_source \
          "$transaction" \
          ingress
      )" || return 1

      ingress_verifier="$recovery/scripts/verify-ingress.sh"

      [[ -f "$ingress_verifier" && -x "$ingress_verifier" ]] || {
        printf \
          'ERROR: historical rollback ingress verifier is unavailable: %s\n' \
          "$ingress_verifier" >&2
        return 1
      }

      ATLAS_VERIFY_INGRESS_VERIFIER="$ingress_verifier" \
        atlas_command_verify || return 1

      ATLAS_PROJECT_DIR="$recovery" \
        "$ingress_verifier" || return 1
      ;;
    *)
      printf \
        'ERROR: unsupported rollback verification scope: %s\n' \
        "$scope" >&2
      return 1
      ;;
  esac

  # Notifications adoption leaves the legacy-mounted worker unchanged.
  # Check the previous baseline during private and public rollback
  # verification, without restoring or recreating that worker.
  previous_id="$(
    atlas_deployment_record_value "$transaction" previous_baseline
  )" || return 1

  baseline="$(
    atlas_deployment_record_dir "$previous_id"
  )" || return 1

  notifications_commit="$(
    atlas_deployment_record_value "$baseline" notifications_commit
  )" || return 1

  if [[ -n "$notifications_commit" ]]; then
    [[ "$notifications_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'ERROR: rollback Notifications source identity is invalid.' >&2
      return 1
    }

    [[ -f "$baseline/status" &&
      "$(<"$baseline/status")" == verified ]] || {
        echo 'ERROR: rollback Notifications baseline is not verified.' >&2
        return 1
      }

    atlas_deployment_verify_runtime "$baseline" || {
      echo 'ERROR: rollback Notifications baseline attestation failed.' >&2
      return 1
    }
  fi
}

atlas_deployment_rollback() {
  local exclusion_fd
  local status

  atlas_execution_exclusion_acquire exclusion_fd || return 1

  if atlas_deployment_rollback_locked "$@"; then
    status=0
  else
    status=$?
  fi

  if ! atlas_execution_exclusion_release "$exclusion_fd"; then
    echo \
      'CRITICAL: unable to release deployment/Scheduler exclusion lock.' \
      >&2

    [[ "$status" -ne 0 ]] || status=1
  fi

  return "$status"
}

atlas_deployment_rollback_locked() {
  local identifier="$1"
  local transaction
  local previous_id
  local baseline
  local scope
  local migration
  local status
  local current_id
  local backup_file
  local acquired=false

  atlas_deployment_valid_id "$identifier" || {
    echo 'ERROR: invalid deployment identifier.' >&2
    return 2
  }
  atlas_deployment_validate_source || return 1
  transaction="$(atlas_deployment_record_dir "$identifier")" || return 1
  [[ -d "$transaction" && -f "$transaction/metadata" && -f "$transaction/status" ]] || return 1

  status="$(<"$transaction/status")"
  [[ "$status" == 'failed' || "$status" == 'verified' ]] || {
    printf 'ERROR: deployment %s is not rollback-eligible (%s).\n' "$identifier" "$status" >&2
    return 1
  }

  migration="$(atlas_deployment_record_value "$transaction" migration)"
  [[ "$migration" == 'none' ]] || {
    echo 'ERROR: automatic rollback is blocked for state-changing migrations.' >&2
    return 1
  }

  previous_id="$(atlas_deployment_record_value "$transaction" previous_baseline)"
  baseline="$(atlas_deployment_record_dir "$previous_id")" || return 1
  [[ -f "$baseline/status" && "$(<"$baseline/status")" == 'verified' ]] || return 1

  current_id="$(atlas_deployment_current_id)" || return 1
  if [[ "$status" == 'verified' && "$current_id" != "$identifier" ]]; then
    echo 'ERROR: refusing to rollback a deployment that is no longer current.' >&2
    return 1
  fi
  if [[ "$status" == 'failed' && "$current_id" != "$previous_id" ]]; then
    echo 'ERROR: failed deployment no longer points at the current baseline.' >&2
    return 1
  fi

  [[ -f "$transaction/backup_file" ]] || {
    echo 'ERROR: rollback requires the recorded pre-update backup.' >&2
    return 1
  }
  IFS= read -r backup_file < "$transaction/backup_file"
  [[ -f "$backup_file" ]] && tar -tzf "$backup_file" >/dev/null 2>&1 || {
    echo 'ERROR: recorded pre-update backup is unavailable or invalid.' >&2
    return 1
  }

  while IFS='|' read -r _ _ _ _ _ _ image_id; do
    docker image inspect "$image_id" >/dev/null 2>&1 || {
      printf 'ERROR: rollback image unavailable: %s\n' "$image_id" >&2
      return 1
    }
  done < "$baseline/images.tsv"

  if [[ -d "$(atlas_deployment_lock_dir)" ]]; then
    atlas_deployment_lock_matches "$identifier" || {
      echo 'ERROR: another deployment owns the active lock.' >&2
      return 1
    }
  else
    atlas_deployment_acquire_lock "$identifier" || return 1
    acquired=true
  fi

  if ! atlas_command_maintenance enable; then
    [[ "$acquired" == true ]] && atlas_deployment_release_lock "$identifier"
    return 1
  fi

  scope="$(atlas_deployment_record_value "$transaction" scope)"
  case "$scope" in
    core)
      atlas_deployment_restore_surface "$baseline" "$transaction" core || return 1
      ;;
    ingress)
      atlas_deployment_restore_surface "$baseline" "$transaction" ingress || return 1
      ;;
    all)
      atlas_deployment_restore_surface "$baseline" "$transaction" core || return 1
      atlas_deployment_restore_surface "$baseline" "$transaction" ingress || return 1

      if [[ -n "$(
        atlas_deployment_record_value \
          "$baseline" \
          sports_commit
      )" ]]; then
        atlas_deployment_restore_surface "$baseline" "$transaction" sports || return 1
      fi
      ;;
    *)
      return 1
      ;;
  esac

  if [[ "$scope" == 'ingress' || "$scope" == 'all' ]]; then
    docker restart atlas-caddy >/dev/null || {
      echo 'ERROR: unable to activate restored Caddy ingress configuration.' >&2
      return 1
    }

    echo 'Post-restore ingress readiness:'
    atlas_deployment_wait_for_ingress_readiness || {
      echo 'ERROR: rollback ingress readiness failed.' >&2
      return 1
    }
  fi

  atlas_deployment_verify_rollback_runtime     "$transaction"     "$scope" || return 1

  atlas_command_maintenance disable || return 1

  atlas_deployment_verify_rollback_runtime     "$transaction"     "$scope" || {
      atlas_command_maintenance enable || true
      return 1
    }

  atlas_deployment_set_current "$previous_id" || {
    atlas_command_maintenance enable || true
    return 1
  }
  atlas_deployment_set_status "$transaction" rolled_back || {
    atlas_command_maintenance enable || true
    return 1
  }
  atlas_deployment_release_lock "$identifier" || return 1

  printf 'Rollback complete: %s -> %s\n' "$identifier" "$previous_id"
}

atlas_deployment_recover_failed_after_apply() {
  local identifier="$1"
  local transaction
  local transaction_type
  local status
  local migration
  local previous_id
  local baseline
  local current_id
  local backup_file
  local target_commit
  local source_commit
  local core_commit
  local ingress_commit
  local sports_commit
  local notifications_commit
  local notifications_evidence
  local -a notifications_rows=()
  local reconciliation_id
  local reconciliation
  local temporary

  atlas_deployment_valid_id "$identifier" || {
    echo 'ERROR: invalid deployment identifier.' >&2
    return 2
  }

  atlas_deployment_validate_source || return 1

  transaction="$(
    atlas_deployment_record_dir "$identifier"
  )" || return 1

  [[ -d "$transaction" && -f "$transaction/metadata" && -f "$transaction/status" ]] || {
    printf \
      'ERROR: deployment record is incomplete: %s\n' \
      "$identifier" >&2
    return 1
  }

  transaction_type="$(
    atlas_deployment_record_value \
      "$transaction" \
      type
  )"

  status="$(<"$transaction/status")"

  [[ "$transaction_type" == 'update' && "$status" == 'failed' ]] || {
    printf \
      'ERROR: deployment %s is not failed-after-apply recovery eligible (type=%s status=%s).\n' \
      "$identifier" \
      "${transaction_type:-unknown}" \
      "${status:-unknown}" >&2
    return 1
  }

  migration="$(
    atlas_deployment_record_value \
      "$transaction" \
      migration
  )"

  [[ "$migration" == 'none' ]] || {
    echo \
      'ERROR: failed-after-apply recovery requires migration=none.' \
      >&2
    return 1
  }

  [[ -f "$transaction/backup_file" ]] || {
    echo \
      'ERROR: failed-after-apply recovery requires the recorded pre-update backup.' \
      >&2
    return 1
  }

  IFS= read -r backup_file < "$transaction/backup_file"

  [[ -f "$backup_file" ]] &&
    tar -tzf "$backup_file" >/dev/null 2>&1 || {
      echo \
        'ERROR: recorded pre-update backup is unavailable or invalid.' \
        >&2
      return 1
    }

  previous_id="$(
    atlas_deployment_record_value \
      "$transaction" \
      previous_baseline
  )"

  atlas_deployment_valid_id "$previous_id" || {
    echo \
      'ERROR: failed transaction has an invalid previous baseline identity.' \
      >&2
    return 1
  }

  baseline="$(
    atlas_deployment_record_dir "$previous_id"
  )" || return 1

  [[ -d "$baseline" && -f "$baseline/status" ]] || {
    echo \
      'ERROR: previous deployment baseline is unavailable.' \
      >&2
    return 1
  }

  [[ "$(<"$baseline/status")" == 'verified' ]] || {
    echo \
      'ERROR: previous deployment baseline is not verified.' \
      >&2
    return 1
  }

  current_id="$(
    atlas_deployment_current_id
  )" || {
    echo \
      'ERROR: current deployment baseline cannot be resolved.' \
      >&2
    return 1
  }

  [[ "$current_id" == "$previous_id" ]] || {
    echo \
      'ERROR: failed deployment no longer points at the current baseline.' \
      >&2
    return 1
  }

  [[ -d "$(atlas_deployment_lock_dir)" ]] || {
    echo \
      'ERROR: failed-after-apply recovery requires the original deployment lock.' \
      >&2
    return 1
  }

  atlas_deployment_lock_matches "$identifier" || {
    echo \
      'ERROR: another deployment owns the active lock.' \
      >&2
    return 1
  }

  [[ -f "$(atlas_maintenance_flag)" ]] || {
    echo \
      'ERROR: failed-after-apply recovery requires maintenance mode to remain enabled.' \
      >&2
    return 1
  }

  target_commit="$(
    atlas_deployment_record_value \
      "$transaction" \
      target_commit
  )"

  source_commit="$(
    atlas_deployment_record_value \
      "$transaction" \
      source_commit
  )"

  if [[ -z "$source_commit" ]]; then
    source_commit="$target_commit"
  fi

  core_commit="$(
    atlas_deployment_record_value \
      "$transaction" \
      core_commit
  )"

  ingress_commit="$(
    atlas_deployment_record_value \
      "$transaction" \
      ingress_commit
  )"

  sports_commit="$(
    atlas_deployment_record_value \
      "$transaction" \
      sports_commit
  )"

  notifications_commit="$(
    atlas_deployment_record_value \
      "$transaction" \
      notifications_commit
  )" || return 1

  if [[ -n "$notifications_commit" ]]; then
    [[ "$notifications_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo 'ERROR: failed transaction Notifications commit is invalid.' >&2
      return 1
    }
  fi

  for commit in \
    "$target_commit" \
    "$source_commit" \
    "$core_commit" \
    "$ingress_commit"
  do
    [[ "$commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo \
        'ERROR: failed transaction target source identity is invalid.' \
        >&2
      return 1
    }
  done

  if [[ -n "$sports_commit" ]]; then
    [[ "$sports_commit" =~ ^[0-9a-f]{40}$ ]] || {
      echo \
        'ERROR: failed transaction Sports source identity is invalid.' \
        >&2
      return 1
    }
  fi

  [[ -s "$transaction/core-source.tar.gz" ]] || {
    echo \
      'ERROR: failed transaction Core source archive is unavailable.' \
      >&2
    return 1
  }

  [[ -s "$transaction/ingress-source.tar.gz" ]] || {
    echo \
      'ERROR: failed transaction Ingress source archive is unavailable.' \
      >&2
    return 1
  }

  if [[ -n "$sports_commit" ]]; then
    [[ -s "$transaction/sports-source.tar.gz" ]] || {
      echo \
        'ERROR: failed transaction Sports source archive is unavailable.' \
        >&2
      return 1
    }
  fi

  [[ -s "$transaction/images.tsv" ]] || {
    echo \
      'ERROR: failed transaction applied target image evidence is unavailable.' \
      >&2
    return 1
  }

  if [[ -n "$notifications_commit" ]]; then
    [[ -s "$transaction/notifications-source.tar.gz" ]] &&
      [[ -s "$transaction/notifications-image.tsv" ]] &&
      [[ -s "$transaction/notifications-source-commit" ]] || {
        echo 'ERROR: failed transaction Notifications evidence is missing.' >&2
        return 1
      }

    [[ "$(<"$transaction/notifications-source-commit")" == \
      "$notifications_commit" ]] || {
        echo 'ERROR: failed transaction Notifications source commit differs.' >&2
        return 1
      }

    mapfile -t notifications_rows \
      < "$transaction/notifications-image.tsv" || return 1

    [[ "${#notifications_rows[@]}" -eq 1 ]] || {
      echo 'ERROR: failed transaction Notifications image evidence is not a single row.' >&2
      return 1
    }

    [[ "${notifications_rows[0]}" == \
      'notifications|modules/notifications/docker-compose.yml|notifications|atlas-notifications-worker|/atlas-notifications-worker|'* ]] || {
        echo 'ERROR: failed transaction Notifications image identity is invalid.' >&2
        return 1
      }

    [[ "$(grep -c '^notifications|' "$transaction/images.tsv")" -eq 1 ]] &&
      [[ "$(grep -Fxc -- \
        "${notifications_rows[0]}" \
        "$transaction/images.tsv")" -eq 1 ]] || {
        echo 'ERROR: failed transaction Notifications image evidence differs from manifest.' >&2
        return 1
      }
  fi

  reconciliation_id="$(
    atlas_deployment_new_id baseline-reconciliation
  )"

  reconciliation="$(
    atlas_deployment_record_dir "$reconciliation_id"
  )" || return 1

  [[ ! -e "$reconciliation" ]] || {
    printf \
      'ERROR: reconciliation baseline already exists: %s\n' \
      "$reconciliation_id" >&2
    return 1
  }

  temporary="$(
    mktemp -d \
      "$(atlas_deployment_records_dir)/.${reconciliation_id}.XXXXXX"
  )" || return 1

  cp -- \
    "$transaction/core-source.tar.gz" \
    "$temporary/core-source.tar.gz" || {
      rm -rf -- "$temporary"
      return 1
    }

  cp -- \
    "$transaction/ingress-source.tar.gz" \
    "$temporary/ingress-source.tar.gz" || {
      rm -rf -- "$temporary"
      return 1
    }

  if [[ -n "$sports_commit" ]]; then
    cp -- \
      "$transaction/sports-source.tar.gz" \
      "$temporary/sports-source.tar.gz" || {
        rm -rf -- "$temporary"
        return 1
      }
  fi

  cp -- \
    "$transaction/images.tsv" \
    "$temporary/images.tsv" || {
      rm -rf -- "$temporary"
      return 1
    }

  if [[ -n "$notifications_commit" ]]; then
    for notifications_evidence in \
      notifications-source.tar.gz \
      notifications-image.tsv \
      notifications-source-commit
    do
      cp -- \
        "$transaction/$notifications_evidence" \
        "$temporary/$notifications_evidence" || {
          rm -rf -- "$temporary"
          return 1
        }

      cmp -s -- \
        "$transaction/$notifications_evidence" \
        "$temporary/$notifications_evidence" || {
          rm -rf -- "$temporary"
          return 1
        }
    done
  fi

  cat > "$temporary/metadata" <<EOF
type=baseline
deployment_id=$reconciliation_id
baseline_kind=failed-after-apply-reconciliation
previous_baseline=$previous_id
failed_deployment=$identifier
target_commit=$target_commit
source_commit=$source_commit
core_commit=$core_commit
ingress_commit=$ingress_commit
sports_commit=$sports_commit
notifications_commit=$notifications_commit
scope=all
migration=none
reason=failed-after-apply-recovery
source_claim=verified-already-applied-target
created_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  cat > "$temporary/provenance" <<EOF
reconciliation_reason=failed-after-apply-recovery
failed_deployment=$identifier
authoritative_previous_baseline=$previous_id
target_commit=$target_commit
source_commit=$source_commit
core_commit=$core_commit
ingress_commit=$ingress_commit
sports_commit=$sports_commit
notifications_commit=$notifications_commit
source_claim=verified-already-applied-target
EOF

  echo 'Private applied-target runtime verification:'

  atlas_deployment_verify_runtime "$temporary" || {
    rm -rf -- "$temporary"
    echo \
      'ERROR: live runtime does not match the failed transaction target.' \
      >&2
    return 1
  }

  atlas_command_doctor || {
    rm -rf -- "$temporary"
    echo \
      'ERROR: private failed-after-apply doctor verification failed.' \
      >&2
    return 1
  }

  atlas_command_verify || {
    rm -rf -- "$temporary"
    echo \
      'ERROR: private failed-after-apply Atlas verification failed.' \
      >&2
    return 1
  }

  if ! atlas_command_maintenance disable; then
    rm -rf -- "$temporary"
    echo \
      'ERROR: unable to reopen public traffic during failed-after-apply recovery.' \
      >&2
    return 1
  fi

  echo 'Public applied-target runtime verification:'

  atlas_deployment_verify_runtime "$temporary" || {
    atlas_command_maintenance enable || true
    rm -rf -- "$temporary"
    echo \
      'ERROR: public applied-target runtime verification failed; maintenance restored.' \
      >&2
    return 1
  }

  atlas_command_doctor || {
    atlas_command_maintenance enable || true
    rm -rf -- "$temporary"
    echo \
      'ERROR: public failed-after-apply doctor verification failed; maintenance restored.' \
      >&2
    return 1
  }

  atlas_command_verify || {
    atlas_command_maintenance enable || true
    rm -rf -- "$temporary"
    echo \
      'ERROR: public failed-after-apply Atlas verification failed; maintenance restored.' \
      >&2
    return 1
  }

  atlas_deployment_set_status \
    "$temporary" \
    verified || {
      atlas_command_maintenance enable || true
      rm -rf -- "$temporary"
      return 1
    }

  (
    cd "$temporary"

    sha256sum \
      images.tsv \
      status \
      metadata \
      provenance \
      core-source.tar.gz \
      ingress-source.tar.gz \
      > MANIFEST.sha256

    if [[ -f sports-source.tar.gz ]]; then
      sha256sum \
        sports-source.tar.gz \
        >> MANIFEST.sha256
    fi

    if [[ -n "$notifications_commit" ]]; then
      sha256sum \
        notifications-source.tar.gz \
        notifications-image.tsv \
        notifications-source-commit \
        >> MANIFEST.sha256
    fi

    sha256sum \
      -c \
      MANIFEST.sha256 \
      >&2
  ) || {
    atlas_command_maintenance enable || true
    rm -rf -- "$temporary"
    return 1
  }

  mv -- \
    "$temporary" \
    "$reconciliation" || {
      atlas_command_maintenance enable || true
      rm -rf -- "$temporary"
      return 1
    }

  atlas_deployment_set_current "$reconciliation_id" || {
    atlas_command_maintenance enable || true
    echo \
      'ERROR: unable to publish failed-after-apply reconciliation baseline as current; maintenance restored.' \
      >&2
    return 1
  }

  if ! atlas_deployment_release_lock "$identifier"; then
    atlas_command_maintenance enable || true
    echo \
      'ERROR: unable to release failed deployment lock; maintenance restored.' \
      >&2
    return 1
  fi

  printf \
    'Failed-after-apply recovery complete: %s -> %s\n' \
    "$identifier" \
    "$reconciliation_id"
}



atlas_deployment_recover_failed_before_apply() {
  local identifier="$1"
  local transaction
  local transaction_type
  local status
  local migration
  local previous_id
  local baseline
  local current_id

  atlas_deployment_valid_id "$identifier" || {
    echo 'ERROR: invalid deployment identifier.' >&2
    return 2
  }

  atlas_deployment_validate_source || return 1

  transaction="$(atlas_deployment_record_dir "$identifier")" || return 1

  [[ -d "$transaction" && -f "$transaction/metadata" && -f "$transaction/status" ]] || {
    printf 'ERROR: deployment record is incomplete: %s\n' "$identifier" >&2
    return 1
  }

  transaction_type="$(atlas_deployment_record_value "$transaction" type)"
  status="$(<"$transaction/status")"

  [[ "$transaction_type" == 'update' && "$status" == 'failed' ]] || {
    printf \
      'ERROR: deployment %s is not failed-before-apply recovery eligible (type=%s status=%s).\n' \
      "$identifier" \
      "${transaction_type:-unknown}" \
      "${status:-unknown}" >&2
    return 1
  }

  migration="$(atlas_deployment_record_value "$transaction" migration)"
  [[ "$migration" == 'none' ]] || {
    echo 'ERROR: failed-before-apply recovery requires migration=none.' >&2
    return 1
  }

  # In the canonical update transaction, backup_file is recorded before
  # the runtime apply stage is invoked. Its absence therefore proves that
  # the canonical apply stage was never entered.
  [[ ! -e "$transaction/backup_file" ]] || {
    echo 'ERROR: failed-before-apply recovery refuses a transaction with a recorded pre-update backup.' >&2
    return 1
  }

  previous_id="$(atlas_deployment_record_value "$transaction" previous_baseline)"

  atlas_deployment_valid_id "$previous_id" || {
    echo 'ERROR: failed transaction has an invalid previous baseline identity.' >&2
    return 1
  }

  baseline="$(atlas_deployment_record_dir "$previous_id")" || return 1

  [[ -d "$baseline" && -f "$baseline/status" ]] || {
    echo 'ERROR: previous deployment baseline is unavailable.' >&2
    return 1
  }

  [[ "$(<"$baseline/status")" == 'verified' ]] || {
    echo 'ERROR: previous deployment baseline is not verified.' >&2
    return 1
  }

  current_id="$(atlas_deployment_current_id)" || {
    echo 'ERROR: current deployment baseline cannot be resolved.' >&2
    return 1
  }

  [[ "$current_id" == "$previous_id" ]] || {
    echo 'ERROR: failed deployment no longer points at the current baseline.' >&2
    return 1
  }

  [[ -d "$(atlas_deployment_lock_dir)" ]] || {
    echo 'ERROR: failed-before-apply recovery requires the original deployment lock.' >&2
    return 1
  }

  atlas_deployment_lock_matches "$identifier" || {
    echo 'ERROR: another deployment owns the active lock.' >&2
    return 1
  }

  [[ -f "$(atlas_maintenance_flag)" ]] || {
    echo 'ERROR: failed-before-apply recovery requires maintenance mode to remain enabled.' >&2
    return 1
  }

  # The unchanged verified baseline must still describe the live runtime
  # before public traffic is reopened.
  atlas_deployment_verify_runtime "$baseline" || {
    echo 'ERROR: production runtime differs from the verified previous baseline.' >&2
    return 1
  }

  atlas_command_doctor || {
    echo 'ERROR: pre-recovery doctor verification failed.' >&2
    return 1
  }

  if ! atlas_command_maintenance disable; then
    echo 'ERROR: unable to reopen public traffic during failed-before-apply recovery.' >&2
    return 1
  fi

  atlas_command_doctor || {
    atlas_command_maintenance enable || true
    echo 'ERROR: public post-recovery doctor verification failed; maintenance restored.' >&2
    return 1
  }

  atlas_deployment_verify_runtime "$baseline" || {
    atlas_command_maintenance enable || true
    echo 'ERROR: runtime drift detected after reopening public traffic; maintenance restored.' >&2
    return 1
  }

  atlas_deployment_set_status "$transaction" recovered_pre_apply || {
    atlas_command_maintenance enable || true
    echo 'ERROR: unable to record failed-before-apply recovery status; maintenance restored.' >&2
    return 1
  }

  if ! atlas_deployment_release_lock "$identifier"; then
    atlas_command_maintenance enable || true
    atlas_deployment_set_status "$transaction" failed || true

    echo 'ERROR: unable to release recovered deployment lock; maintenance restored.' >&2
    return 1
  fi

  printf \
    'Failed-before-apply recovery complete: %s -> %s\n' \
    "$identifier" \
    "$previous_id"
}


atlas_command_deployment() {
  local action="${1:-status}"
  case "$action" in
    status)
      atlas_deployment_status
      ;;
    baseline)
      atlas_deployment_baseline
      ;;
    adopt-sports)
      atlas_deployment_adopt_sports
      ;;
    adopt-notifications)
      shift
      atlas_deployment_adopt_notifications_guarded "$@"
      ;;
    recover-failed-before-apply)
      [[ -n "${2:-}" ]] || {
        echo 'Usage: atlas deployment recover-failed-before-apply <deployment-id>' >&2
        return 2
      }
      atlas_deployment_recover_failed_before_apply "$2"
      ;;
    recover-failed-after-apply)
      [[ -n "${2:-}" ]] || {
        echo 'Usage: atlas deployment recover-failed-after-apply <deployment-id>' >&2
        return 2
      }
      atlas_deployment_recover_failed_after_apply "$2"
      ;;
    recover-failed-rollback)
      [[ -n "${2:-}" ]] || {
        echo 'Usage: atlas deployment recover-failed-rollback <deployment-id>' >&2
        return 2
      }
      atlas_deployment_recover_failed_rollback "$2"
      ;;
    rollback)
      [[ -n "${2:-}" ]] || {
        echo 'Usage: atlas deployment rollback <deployment-id>' >&2
        return 2
      }
      atlas_deployment_rollback "$2"
      ;;
    help|-h|--help)
      cat <<'HELP'
Usage:
  atlas deployment status
  atlas deployment baseline
  atlas deployment adopt-sports
  atlas deployment adopt-notifications
  atlas deployment recover-failed-before-apply <deployment-id>
  atlas deployment recover-failed-after-apply <deployment-id>
  atlas deployment recover-failed-rollback <deployment-id>
  atlas deployment rollback <deployment-id>

Notifications adoption records and attests the existing historical worker.
It does not launch, upgrade, relocate, or restore Notifications. Managed
Notifications deployment requires a separate verified lifecycle contract.

Baseline creation records verified production source archives and exact running
image identities. Sports adoption creates a new verified baseline by preserving
the current Core/Ingress source evidence while adding the exact live Sports
source and running image identities. Failed-before-apply recovery only clears a held failed update
after proving the previous verified baseline is still current and unchanged.
Failed-after-apply recovery verifies an already-applied target without repeating
runtime apply, publishes a separate verified reconciliation baseline, and preserves
the original failed transaction as immutable evidence.
Failed-rollback recovery finalizes an already restored failed rollback by
publishing a separate verified reconciliation baseline while preserving the
original failed transaction as immutable evidence. Rollback restores only a
directly related known-good baseline.
HELP
      ;;
    *)
      printf 'Unknown deployment action: %s\n' "$action" >&2
      return 2
      ;;
  esac
}
