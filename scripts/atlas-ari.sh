#!/usr/bin/env bash
set -euo pipefail

ATLAS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ATLAS_CONFIG_FILE="$ATLAS_ROOT/config/atlas.conf"

if [[ ! -f "$ATLAS_CONFIG_FILE" ]]; then
  echo "Missing Atlas config: $ATLAS_CONFIG_FILE"
  exit 1
fi

source "$ATLAS_CONFIG_FILE"

ATLAS_ENV_FILE="$ATLAS_ROOT/.env"
if [[ -f "$ATLAS_ENV_FILE" ]]; then
  source "$ATLAS_ENV_FILE"
fi

ARI_DATA_DIR="$ATLAS_ARI_DIR"
ARI_SNAPSHOT_DIR="$ATLAS_ARI_SNAPSHOT_DIR"
LATEST_FILE="$ATLAS_ARI_LATEST_FILE"
MEDIA_ROOT="$ATLAS_MEDIA_ROOT"

usage() {
  cat <<EOF
Atlas Retention Intelligence

Usage:
  atlas-ari.sh collect
  atlas-ari.sh report
EOF
}

collect() {
  mkdir -p "$ARI_SNAPSHOT_DIR"

  local timestamp
  timestamp="$(date -Iseconds)"

  local atlas_version
  atlas_version="$(cat "$ATLAS_PROJECT_DIR/VERSION" 2>/dev/null || echo "unknown")"

  local hostname
  hostname="$(hostname)"

  local schema_version
  schema_version=1

  local safe_timestamp
  safe_timestamp="$(date +"%Y-%m-%dT%H-%M-%S%z")"

  local snapshot_file
  snapshot_file="$ARI_SNAPSHOT_DIR/$safe_timestamp.json"

  local storage_capacity storage_used storage_available storage_use_percent
  storage_capacity="$(df -h "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $2}')"
  storage_used="$(df -h "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $3}')"
  storage_available="$(df -h "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"
  storage_use_percent="$(df -h "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {gsub("%","",$5); print $5}')"

  local jellyfin_info jellyfin_server_name jellyfin_version jellyfin_id
  jellyfin_info="{}"

  if [[ -n "${ATLAS_JELLYFIN_API_KEY:-}" ]]; then
  jellyfin_info="$(curl -s \
    -H "X-Emby-Token: $ATLAS_JELLYFIN_API_KEY" \
    "$ATLAS_JELLYFIN_URL/System/Info" || echo "{}")"
  fi

  local jellyfin_libraries jellyfin_library_summary
  jellyfin_libraries="[]"

  if [[ -n "${ATLAS_JELLYFIN_API_KEY:-}" ]]; then
  jellyfin_libraries="$(curl -s \
    -H "X-Emby-Token: $ATLAS_JELLYFIN_API_KEY" \
    "$ATLAS_JELLYFIN_URL/Library/VirtualFolders" || echo "[]")"
  fi

  jellyfin_library_summary="$(
  echo "$jellyfin_libraries" | jq '
  map({
  name: .Name,
  type: .CollectionType,
  path: .Locations[0],
  status: .RefreshStatus
  })'
  )"

  local jellyfin_users jellyfin_user_summary
  jellyfin_users="[]"

  if [[ -n "${ATLAS_JELLYFIN_API_KEY:-}" ]]; then
  jellyfin_users="$(curl -s \
    -H "X-Emby-Token: $ATLAS_JELLYFIN_API_KEY" \
    "$ATLAS_JELLYFIN_URL/Users" || echo "[]")"
  fi

  jellyfin_user_summary="$(
  echo "$jellyfin_users" | jq '
  map({
    name: .Name,
    id: .Id,
    administrator: (.Policy.IsAdministrator // false),
    disabled: (.Policy.IsDisabled // false),
    hidden: (.Policy.IsHidden // false),
    last_activity: (.LastActivityDate // null)
})'
)"

  jellyfin_server_name="$(echo "$jellyfin_info" | jq -r '.ServerName // "unknown"')"
  jellyfin_version="$(echo "$jellyfin_info" | jq -r '.Version // "unknown"')"
  jellyfin_id="$(echo "$jellyfin_info" | jq -r '.Id // "unknown"')"

  local movie_count tv_count anime_movie_count anime_tv_count

  movie_count="$(find "$MEDIA_ROOT/Movies" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
  tv_count="$(find "$MEDIA_ROOT/TV" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
  anime_movie_count="$(find "$MEDIA_ROOT/Anime Movies" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
  anime_tv_count="$(find "$MEDIA_ROOT/Anime TV" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"

  cat > "$snapshot_file" <<EOF
{
  "timestamp": "$timestamp",

  "atlas": {
    "version": "$atlas_version",
    "hostname": "$hostname",
    "schema_version": $schema_version
  },

  "storage": {
    "media_root": "$MEDIA_ROOT",
    "capacity": "$storage_capacity",
    "used": "$storage_used",
    "available": "$storage_available",
    "utilization_percent": $storage_use_percent
  },

  "jellyfin": {
  "server_name": "$jellyfin_server_name",
  "version": "$jellyfin_version",
  "id": "$jellyfin_id",
  "libraries": $jellyfin_library_summary,
  "users": $jellyfin_user_summary
  },

  "libraries": {
    "movies": {
      "count": $movie_count
    },
    "tv": {
      "count": $tv_count
    },
    "anime_movies": {
      "count": $anime_movie_count
    },
    "anime_tv": {
      "count": $anime_tv_count
    }
  }
}
EOF

  echo "ARI collection complete."
  cp "$snapshot_file" "$LATEST_FILE"
  echo "Snapshot written to: $snapshot_file"
  echo "Latest snapshot updated: $LATEST_FILE"
}

report() {
  if [[ ! -f "$LATEST_FILE" ]]; then
    echo "No ARI snapshot found."
    echo "Run: atlas ari collect"
    exit 1
  fi

  echo "Atlas Retention Intelligence Report"
  echo "-----------------------------------"
  echo

  jq -r '
  "Atlas",
  "------",
  "Version: \(.atlas.version)",
  "Host: \(.atlas.hostname)",
  "Schema: \(.atlas.schema_version)",
  "",
  "Storage",
  "-------",
  "Media Root: \(.storage.media_root)",
  "Capacity:   \(.storage.capacity)",
  "Used:       \(.storage.used)",
  "Available:  \(.storage.available)",
  "Usage:      \(.storage.utilization_percent)%",
  "",
  "Jellyfin",
  "--------",
  "Server:  \(.jellyfin.server_name // "unknown")",
  "Version: \(.jellyfin.version // "unknown")",
  "ID:      \(.jellyfin.id // "unknown")",
  "Library Count: \((.jellyfin.libraries // []) | length)",
  "",
  "Jellyfin Libraries",
  "------------------",
  ((.jellyfin.libraries // [])[] | "  - \(.name) [\(.type)] → \(.path) (\(.status))"),
  "",
  "Jellyfin Users",
  "--------------",
  "User Count: \((.jellyfin.users // []) | length)",
  ((.jellyfin.users // [])[] | "  - \(.name) | admin=\(.administrator) disabled=\(.disabled) hidden=\(.hidden) last_activity=\(.last_activity // "never")"),
  "",
  "Libraries",
  "---------",
  "Movies:        \(.libraries.movies.count)",
  "TV:            \(.libraries.tv.count)",
  "Anime Movies:  \(.libraries.anime_movies.count)",
  "Anime TV:      \(.libraries.anime_tv.count)"
  ' "$LATEST_FILE"

print_library_validation
print_library_path_validation
}

print_library_validation() {
  echo
  echo "Library Validation"
  echo "------------------"

  local expected_libraries=(
    "Movies"
    "TV"
    "Anime Movies"
    "Anime TV"
  )

  for library in "${expected_libraries[@]}"; do
    if validate_jellyfin_libraries | grep -Fxq "$library"; then
      echo "✓ $library"
    else
      echo "✗ $library"
    fi
  done
}

print_library_path_validation() {
  echo
  echo "Library Path Validation"
  echo "-----------------------"

  local library_checks=(
    "Movies:$ATLAS_JELLYFIN_MOVIES_PATH"
    "TV:$ATLAS_JELLYFIN_TV_PATH"
    "Anime Movies:$ATLAS_JELLYFIN_ANIME_MOVIES_PATH"
    "Anime TV:$ATLAS_JELLYFIN_ANIME_TV_PATH"
  )

  for check in "${library_checks[@]}"; do
    local library="${check%%:*}"
    local expected_path="${check#*:}"

    local actual_path
    actual_path="$(get_jellyfin_library_path "$library")"

    if [[ "$actual_path" == "$expected_path" ]]; then
      echo "✓ $library"
    else
      echo "✗ $library"
      echo "    Expected: $expected_path"
      echo "    Found:    ${actual_path:-<missing>}"
    fi
  done
}

get_jellyfin_library_path() {
  local library_name="$1"

  jq -r --arg name "$library_name" '
    (.jellyfin.libraries // [])
    | map(select(.name == $name))
    | .[0].path // ""
  ' "$LATEST_FILE"
}

validate_jellyfin_libraries() {
  jq -r '
    (.jellyfin.libraries // [])[].name
  ' "$LATEST_FILE"
}

case "${1:-}" in
  collect)
    collect
    ;;
  report)
    report
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "Unknown ARI command: $1"
    usage
    exit 1
    ;;
esac
