#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Configuration
###############################################################################

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

###############################################################################
# Collection
###############################################################################

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
  local storage_capacity_bytes storage_used_bytes storage_available_bytes

  storage_capacity="$(df -h "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $2}')"
  storage_used="$(df -h "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $3}')"
  storage_available="$(df -h "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"
  storage_use_percent="$(df -h "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {gsub("%","",$5); print $5}')"

  storage_capacity_bytes="$(df -B1 "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $2}')"
  storage_used_bytes="$(df -B1 "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $3}')"
  storage_available_bytes="$(df -B1 "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"

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

  local jellyfin_counts jellyfin_count_summary
  jellyfin_counts="{}"

  if [[ -n "${ATLAS_JELLYFIN_API_KEY:-}" ]]; then
    jellyfin_counts="$(curl -s \
      -H "X-Emby-Token: $ATLAS_JELLYFIN_API_KEY" \
      "$ATLAS_JELLYFIN_URL/Items/Counts" || echo "{}")"
  fi

  jellyfin_count_summary="$(
  echo "$jellyfin_counts" | jq '{
  movies: (.MovieCount // 0),
  series: (.SeriesCount // 0),
  episodes: (.EpisodeCount // 0),
  songs: (.SongCount // 0),
  albums: (.AlbumCount // 0),
  books: (.BookCount // 0),
  total_items: (.ItemCount // 0)
}'
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
    "capacity_bytes": $storage_capacity_bytes,
    "used": "$storage_used",
    "used_bytes": $storage_used_bytes,
    "available": "$storage_available",
    "available_bytes": $storage_available_bytes,
    "utilization_percent": $storage_use_percent
  },

  "jellyfin": {
  "server_name": "$jellyfin_server_name",
  "version": "$jellyfin_version",
  "id": "$jellyfin_id",
  "libraries": $jellyfin_library_summary,
  "users": $jellyfin_user_summary,
  "counts": $jellyfin_count_summary
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

###############################################################################
# Analysis
###############################################################################

print_analysis() {
  print_storage_analysis
  print_library_analysis
}

print_storage_analysis() {
  echo
  echo "Storage Analysis"
  echo "----------------"

  local previous_snapshot
  previous_snapshot="$(get_previous_snapshot)"

  if [[ -z "$previous_snapshot" || ! -f "$previous_snapshot" ]]; then
    echo "No previous snapshot available."
    return
  fi

  local current previous

  current="$(jq -r '.storage.used_bytes // 0' "$LATEST_FILE")"
  previous="$(jq -r '.storage.used_bytes // empty' "$previous_snapshot")"

  if [[ -z "$previous" ]]; then
    echo "Previous snapshot does not contain byte-accurate storage data."
    echo "Run another collection to enable storage growth analysis."
    return
  fi

  local delta
  delta=$((current - previous))

  local current_human previous_human delta_human
  current_human="$(format_bytes "$current")"
  previous_human="$(format_bytes "$previous")"
  delta_human="$(format_bytes "${delta#-}")"

  local direction

  if (( delta > 0 )); then
      direction="Increasing"
  elif (( delta < 0 )); then
      direction="Decreasing"
  else
      direction="Unchanged"
  fi

  local growth

  if (( delta > 0 )); then
      growth="+$delta_human"
  elif (( delta < 0 )); then
      growth="-$delta_human"
  else
      growth="$delta_human"
  fi

  echo "Current Used : $current_human"
  echo "Previous Used: $previous_human"
  echo
  echo "Growth       : $growth"
  echo "Direction    : $direction"
}

print_library_analysis() {
  echo
  echo "Library Analysis"
  echo "----------------"

  local previous_snapshot
  previous_snapshot="$(get_previous_snapshot)"

  if [[ -z "$previous_snapshot" || ! -f "$previous_snapshot" ]]; then
    echo "No previous snapshot available."
    return
  fi

  local current_movies previous_movies
  local current_tv previous_tv

  current_movies="$(jq -r '.libraries.movies.count // 0' "$LATEST_FILE")"
  previous_movies="$(jq -r '.libraries.movies.count // 0' "$previous_snapshot")"

  current_tv="$(jq -r '.libraries.tv.count // 0' "$LATEST_FILE")"
  previous_tv="$(jq -r '.libraries.tv.count // 0' "$previous_snapshot")"

  local movies_delta tv_delta
  movies_delta=$((current_movies - previous_movies))
  tv_delta=$((current_tv - previous_tv))

  local movies_status tv_status

  if (( movies_delta > 0 )); then
    movies_status="Increasing"
  elif (( movies_delta < 0 )); then
    movies_status="Decreasing"
  else
    movies_status="Unchanged"
  fi

  if (( tv_delta > 0 )); then
    tv_status="Increasing"
  elif (( tv_delta < 0 )); then
    tv_status="Decreasing"
  else
    tv_status="Unchanged"
  fi

  echo "Movies"
  echo "  Current : $current_movies"
  echo "  Previous: $previous_movies"
  echo "  Growth  : $movies_delta"
  echo "  Status  : $movies_status"
  echo
  echo "TV"
  echo "  Current : $current_tv"
  echo "  Previous: $previous_tv"
  echo "  Growth  : $tv_delta"
  echo "  Status  : $tv_status"
}

###############################################################################
# Reporting
###############################################################################

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
  "Jellyfin Counts",
  "---------------",
  "Movies:      \(.jellyfin.counts.movies // 0)",
  "Series:      \(.jellyfin.counts.series // 0)",
  "Episodes:    \(.jellyfin.counts.episodes // 0)",
  "Songs:       \(.jellyfin.counts.songs // 0)",
  "Albums:      \(.jellyfin.counts.albums // 0)",
  "Books:       \(.jellyfin.counts.books // 0)",
  "Total Items: \(.jellyfin.counts.total_items // 0)",
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
print_library_synchronization
print_analysis
print_snapshot_comparison
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

print_library_synchronization() {
  local filesystem_movies filesystem_tv
  local jellyfin_movies jellyfin_series

  filesystem_movies="$(jq -r '.libraries.movies.count // 0' "$LATEST_FILE")"
  filesystem_tv="$(jq -r '.libraries.tv.count // 0' "$LATEST_FILE")"

  jellyfin_movies="$(jq -r '.jellyfin.counts.movies // 0' "$LATEST_FILE")"
  jellyfin_series="$(jq -r '.jellyfin.counts.series // 0' "$LATEST_FILE")"

  echo
  echo "Library Synchronization"
  echo "-----------------------"

  if [[ "$filesystem_movies" == "$jellyfin_movies" ]]; then
    echo "✓ Movies synchronized"
  else
    echo "✗ Movies out of sync"
    echo "    Filesystem: $filesystem_movies"
    echo "    Jellyfin:   $jellyfin_movies"
  fi

  if [[ "$filesystem_tv" == "$jellyfin_series" ]]; then
    echo "✓ TV synchronized"
  else
    echo "✗ TV out of sync"
    echo "    Filesystem: $filesystem_tv"
    echo "    Jellyfin:   $jellyfin_series"
  fi
}

print_snapshot_comparison() {
  local previous_snapshot
  previous_snapshot="$(get_previous_snapshot)"

  if [[ -z "$previous_snapshot" || ! -f "$previous_snapshot" ]]; then
    echo
    echo "Snapshot Comparison"
    echo "-------------------"
    echo "No previous snapshot available."
    return 0
  fi

  local current_timestamp previous_timestamp
  current_timestamp="$(jq -r '.timestamp // "unknown"' "$LATEST_FILE")"
  previous_timestamp="$(jq -r '.timestamp // "unknown"' "$previous_snapshot")"

  local current_movies previous_movies
  local current_tv previous_tv
  local current_users previous_users

  current_movies="$(jq -r '.libraries.movies.count // 0' "$LATEST_FILE")"
  previous_movies="$(jq -r '.libraries.movies.count // 0' "$previous_snapshot")"

  current_tv="$(jq -r '.libraries.tv.count // 0' "$LATEST_FILE")"
  previous_tv="$(jq -r '.libraries.tv.count // 0' "$previous_snapshot")"

  current_users="$(jq -r '(.jellyfin.users // []) | length' "$LATEST_FILE")"
  previous_users="$(jq -r '(.jellyfin.users // []) | length' "$previous_snapshot")"

  local current_storage_used previous_storage_used
  local current_storage_used_bytes previous_storage_used_bytes

  current_storage_used="$(jq -r '.storage.used // "unknown"' "$LATEST_FILE")"
  previous_storage_used="$(jq -r '.storage.used // "unknown"' "$previous_snapshot")"

  current_storage_used_bytes="$(jq -r '.storage.used_bytes // 0' "$LATEST_FILE")"
  previous_storage_used_bytes="$(jq -r '.storage.used_bytes // 0' "$previous_snapshot")"

  local changes=0

  if [[ "$current_movies" != "$previous_movies" ]]; then
  changes=$((changes + 1))
  fi

  if [[ "$current_tv" != "$previous_tv" ]]; then
  changes=$((changes + 1))
  fi

  if [[ "$current_users" != "$previous_users" ]]; then
  changes=$((changes + 1))
  fi

  if [[ "$current_storage_used_bytes" != "$previous_storage_used_bytes" ]]; then
  changes=$((changes + 1))
  fi

  echo
  echo "Snapshot Comparison"
  echo "-------------------"
  echo "Previous: $previous_timestamp"
  echo "Current:  $current_timestamp"
  echo
  echo "Summary"
  echo "-------"

  if [[ "$changes" -eq 0 ]]; then
  echo "✓ No operational changes detected."
  else
  echo "⚠ $changes operational change(s) detected."
  fi

  echo
  echo "Details"
  echo "-------"
  echo "Storage Used: $previous_storage_used → $current_storage_used"
  echo "Movies: $previous_movies → $current_movies"
  echo "TV:     $previous_tv → $current_tv"
  echo "Users:  $previous_users → $current_users"
}

###############################################################################
# Helper Functions
###############################################################################

get_jellyfin_library_path() {
  local library_name="$1"

  jq -r --arg name "$library_name" '
    (.jellyfin.libraries // [])
    | map(select(.name == $name))
    | .[0].path // ""
  ' "$LATEST_FILE"
}

get_previous_snapshot() {
  ls -1 "$ARI_SNAPSHOT_DIR"/*.json 2>/dev/null \
    | sort \
    | tail -2 \
    | head -1
}

format_bytes() {
  local bytes="$1"

  numfmt \
    --to=iec \
    --suffix=B \
    --format="%.1f" \
    "$bytes"
}

###############################################################################
# Validation
###############################################################################

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
