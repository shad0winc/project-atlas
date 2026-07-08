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
# Forecast
###############################################################################

print_forecast() {
  echo
  echo "Forecast"
  echo "--------"

  local available_bytes
  available_bytes="$(jq -r '.storage.available_bytes // 0' "$LATEST_FILE")"

  local net_growth
  net_growth="$(metric_storage_net_growth 5)"

  local available_human net_growth_human
  available_human="$(format_bytes "$available_bytes")"
  net_growth_human="$(format_bytes "${net_growth#-}")"

  echo "Storage Available : $available_human"
  echo "Recent Net Growth : $(metric_growth "$net_growth" "$net_growth_human")"

  if (( net_growth <= 0 )); then
    echo "Forecast          : Stable or insufficient growth data"
    return
  fi

  local snapshots
  snapshots="$(get_snapshot_count 5)"

  echo "Snapshots Used    : $snapshots"

    local intervals
  intervals="$(metric_growth_intervals '.storage.used_bytes' 5)"

  local average_interval
  average_interval="$(printf '%s\n' "$intervals" | metric_average)"

  local average_interval_human
  average_interval_human="$(format_bytes "${average_interval#-}")"

  echo "Average Growth    : $(metric_growth "$average_interval" "$average_interval_human") / snapshot"

  local time_intervals
  time_intervals="$(metric_snapshot_time_intervals 5)"

  local average_seconds
  average_seconds="$(printf '%s\n' "$time_intervals" | metric_average)"

  echo "Average Interval  : $average_seconds seconds"

}

###############################################################################
# Health
###############################################################################

print_health() {
  echo
  echo "Atlas Health"
  echo "------------"

  local score=100
  local checks=()
  local warnings=()

  health_register_check "Platform:Storage utilization" "Storage utilization is critically high" 20 health_check_storage
  health_register_check "Platform:Docker engine" "Docker Engine is not responding" 20 health_check_docker
  health_register_check "Platform:Core services" "One or more required services are not running" 20 health_check_containers
  health_register_check "Platform:VPN tunnel" "Gluetun VPN is not healthy" 20 health_check_vpn

  health_register_check "Media:Jellyfin libraries" "Jellyfin library validation failed" 20 validate_jellyfin_libraries
  health_register_check "Media:Jellyfin library paths" "Jellyfin library path validation failed" 20 health_check_library_paths
  health_register_check "Media:Library synchronization" "Library synchronization failed" 20 health_check_library_synchronization

  health_register_check "Intelligence:Snapshot freshness" "ARI snapshot is more than 24 hours old" 10 health_check_snapshot_freshness

  local status="Healthy"

  if (( score < 90 )); then
    status="Warning"
  fi

  if (( score < 70 )); then
    status="Degraded"
  fi

  echo "Score : $score / 100"
  echo "Status: $status"
  echo
  print_health_group "Platform"
  print_health_group "Media"
  print_health_group "Intelligence"

  if (( ${#warnings[@]} > 0 )); then
    echo
    echo "Warnings"
    echo "--------"
    for warning in "${warnings[@]}"; do
      echo "- $warning"
    done
  fi
}

health_register_check() {
  local check_name="$1"
  local warning_message="$2"
  local penalty="$3"
  local check_function="$4"

  if "$check_function" >/dev/null 2>&1; then
    checks+=("$check_name")
  else
    score=$((score - penalty))
    warnings+=("$warning_message")
  fi
}

print_health_group() {
  local group="$1"
  local check item label printed=0

  for check in "${checks[@]}"; do
    item="${check%%:*}"
    label="${check#*:}"

    if [[ "$item" == "$group" ]]; then
      if (( printed == 0 )); then
        echo
        echo "$group"
        printf '%*s\n' "${#group}" '' | tr ' ' '-'
        printed=1
      fi

      echo "✓ $label"
    fi
  done
}

health_check_library_paths() {
  local expected_paths=(
    "Movies:$ATLAS_JELLYFIN_MOVIES_PATH"
    "TV:$ATLAS_JELLYFIN_TV_PATH"
    "Anime Movies:$ATLAS_JELLYFIN_ANIME_MOVIES_PATH"
    "Anime TV:$ATLAS_JELLYFIN_ANIME_TV_PATH"
  )

  local item library expected actual failed=0

  for item in "${expected_paths[@]}"; do
    library="${item%%:*}"
    expected="${item#*:}"
    actual="$(get_jellyfin_library_path "$library")"

    if [[ "$actual" != "$expected" ]]; then
      failed=1
    fi
  done

  return "$failed"
}

health_check_library_synchronization() {
  local movies_count tv_count jellyfin_movies jellyfin_series failed=0

  movies_count="$(jq -r '.libraries.movies.count // 0' "$LATEST_FILE")"
  tv_count="$(jq -r '.libraries.tv.count // 0' "$LATEST_FILE")"
  jellyfin_movies="$(jq -r '.jellyfin.counts.movies // 0' "$LATEST_FILE")"
  jellyfin_series="$(jq -r '.jellyfin.counts.series // 0' "$LATEST_FILE")"

  if [[ "$movies_count" != "$jellyfin_movies" ]]; then
    failed=1
  fi

  if [[ "$tv_count" != "$jellyfin_series" ]]; then
    failed=1
  fi

  return "$failed"
}

health_check_storage() {
  local used_percent

  used_percent="$(jq -r '.storage.utilization_percent // 100' "$LATEST_FILE")"

  if (( used_percent >= 95 )); then
    return 1
  fi

  return 0
}

health_check_containers() {
  local required=(
    jellyfin
    jellyseerr
    prowlarr
    sonarr
    sonarr-anime
    radarr
    radarr-anime
    qbittorrent
    gluetun
    homepage
  )

  local container

  for container in "${required[@]}"; do
    if ! docker inspect \
        --format '{{.State.Running}}' \
        "$container" 2>/dev/null | grep -q true; then
      return 1
    fi
  done

  return 0
}

health_check_vpn() {
  docker inspect \
    --format '{{.State.Health.Status}}' \
    gluetun 2>/dev/null | grep -q healthy
}

health_check_docker() {
  docker info >/dev/null 2>&1
}

health_check_snapshot_freshness() {
  local latest_snapshot

  latest_snapshot="$(stat -c %Y "$LATEST_FILE")"

  local now
  now="$(date +%s)"

  local age
  age=$((now - latest_snapshot))

  if (( age > 86400 )); then
    return 1
  fi

  return 0
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

  print_storage_snapshot_comparison
  print_storage_history
}

print_storage_snapshot_comparison() {
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
  delta="$(metric_delta "$previous" "$current")"

  local current_human previous_human delta_human
  current_human="$(format_bytes "$current")"
  previous_human="$(format_bytes "$previous")"
  delta_human="$(format_bytes "${delta#-}")"

  local direction growth
  direction="$(metric_direction "$delta")"
  growth="$(metric_growth "$delta" "$delta_human")"

  echo "Current Used : $current_human"
  echo "Previous Used: $previous_human"
  echo
  echo "Growth       : $growth"
  echo "Direction    : $direction"
}

print_storage_history() {
  echo
  echo "History"
  echo "-------"

  local snapshot_count
  snapshot_count="$(get_snapshot_count 5)"

  local net_growth
  net_growth="$(metric_storage_net_growth 5)"

  local net_growth_human
  net_growth_human="$(format_bytes "${net_growth#-}")"

  local values
  values="$(metric_history_values '.storage.used_bytes' 5)"

  local average_used minimum_used maximum_used
  average_used="$(printf '%s\n' "$values" | metric_average)"
  minimum_used="$(printf '%s\n' "$values" | metric_min)"
  maximum_used="$(printf '%s\n' "$values" | metric_max)"

  local average_used_human minimum_used_human maximum_used_human
  average_used_human="$(format_bytes "$average_used")"
  minimum_used_human="$(format_bytes "$minimum_used")"
  maximum_used_human="$(format_bytes "$maximum_used")"

  local trend
  trend="$(metric_trend "$net_growth")"

  echo "Snapshots     : $snapshot_count"
  echo "Net Growth    : $(metric_growth "$net_growth" "$net_growth_human")"
  echo
  echo "Average Used  : $average_used_human"
  echo "Minimum Used  : $minimum_used_human"
  echo "Maximum Used  : $maximum_used_human"
  echo "Trend         : $trend"
}

print_library_analysis() {
  echo
  echo "Library Analysis"
  echo "----------------"

  print_library_snapshot_comparison
  print_library_history
}

print_library_snapshot_comparison() {
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
  movies_delta="$(metric_delta "$previous_movies" "$current_movies")"
  tv_delta="$(metric_delta "$previous_tv" "$current_tv")"

  local movies_status tv_status
  movies_status="$(metric_direction "$movies_delta")"
  tv_status="$(metric_direction "$tv_delta")"

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

print_library_history() {
  echo
  echo "History"
  echo "-------"

  local snapshot_count
  snapshot_count="$(get_snapshot_count 5)"

  local movie_values tv_values
  movie_values="$(metric_movie_values 5)"
  tv_values="$(metric_tv_values 5)"

  local movie_growth tv_growth
  movie_growth="$(metric_movie_net_growth 5)"
  tv_growth="$(metric_tv_net_growth 5)"

  local movie_average movie_min movie_max
  movie_average="$(printf '%s\n' "$movie_values" | metric_average)"
  movie_min="$(printf '%s\n' "$movie_values" | metric_min)"
  movie_max="$(printf '%s\n' "$movie_values" | metric_max)"

  local tv_average tv_min tv_max
  tv_average="$(printf '%s\n' "$tv_values" | metric_average)"
  tv_min="$(printf '%s\n' "$tv_values" | metric_min)"
  tv_max="$(printf '%s\n' "$tv_values" | metric_max)"

  echo "Snapshots     : $snapshot_count"
  echo

  echo "Movies"
  echo "  Net Growth  : $movie_growth"
  echo "  Average     : $movie_average"
  echo "  Minimum     : $movie_min"
  echo "  Maximum     : $movie_max"
  echo "  Trend       : $(metric_movie_trend 5)"

  echo

  echo "TV"
  echo "  Net Growth  : $tv_growth"
  echo "  Average     : $tv_average"
  echo "  Minimum     : $tv_min"
  echo "  Maximum     : $tv_max"
  echo "  Trend       : $(metric_tv_trend 5)"
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

print_health
print_forecast
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
# Snapshot Helpers
###############################################################################

get_recent_snapshots() {
  local count="${1:-5}"

  find "$ARI_SNAPSHOT_DIR" \
    -maxdepth 1 \
    -type f \
    -name '*.json' \
    | sort \
    | tail -n "$count"
}

get_snapshot_count() {
  get_recent_snapshots "$1" | wc -l
}

get_oldest_recent_snapshot() {
  local count="${1:-5}"

  get_recent_snapshots "$count" | head -n 1
}

###############################################################################
# Jellyfin Helpers
###############################################################################

get_jellyfin_library_path() {
  local library_name="$1"

  jq -r --arg name "$library_name" '
    (.jellyfin.libraries // [])
    | map(select(.name == $name))
    | .[0].path // ""
  ' "$LATEST_FILE"
}

###############################################################################
# Snapshot Helpers
###############################################################################

get_previous_snapshot() {
  ls -1 "$ARI_SNAPSHOT_DIR"/*.json 2>/dev/null \
    | sort \
    | tail -2 \
    | head -1
}

get_recent_snapshots() {
  local count="${1:-5}"

  find "$ARI_SNAPSHOT_DIR" \
    -maxdepth 1 \
    -type f \
    -name '*.json' \
    | sort \
    | tail -n "$count"
}

get_snapshot_count() {
  get_recent_snapshots "$1" | wc -l
}

get_oldest_recent_snapshot() {
  local count="${1:-5}"

  get_recent_snapshots "$count" | head -n 1
}

###############################################################################
# Formatting Helpers
###############################################################################

format_bytes() {
  local bytes="$1"

  numfmt \
    --to=iec \
    --suffix=B \
    --format="%.1f" \
    "$bytes"
}

###############################################################################
# Metric Helpers
###############################################################################

# Basic Metrics

metric_delta() {
  local previous="$1"
  local current="$2"

  echo $((current - previous))
}

metric_direction() {
  local delta="$1"

  if (( delta > 0 )); then
    echo "Increasing"
  elif (( delta < 0 )); then
    echo "Decreasing"
  else
    echo "Unchanged"
  fi
}

metric_trend() {
  local delta="$1"

  if (( delta > 0 )); then
    echo "Increasing"
  elif (( delta < 0 )); then
    echo "Decreasing"
  else
    echo "Stable"
  fi
}

metric_growth() {
  local delta="$1"
  local formatted="$2"

  if (( delta > 0 )); then
    echo "+$formatted"
  elif (( delta < 0 )); then
    echo "-$formatted"
  else
    echo "$formatted"
  fi
}

# Historical Metrics

metric_history_delta() {
  local jq_path="$1"
  local count="${2:-5}"

  local oldest_snapshot
  oldest_snapshot="$(
    get_recent_snapshots "$count" |
      while read -r snapshot; do
        if jq -e "$jq_path" "$snapshot" >/dev/null 2>&1; then
          echo "$snapshot"
          break
        fi
      done
  )"

  if [[ -z "$oldest_snapshot" || ! -f "$oldest_snapshot" ]]; then
    echo 0
    return
  fi

  local oldest current
  oldest="$(jq -r "$jq_path // 0" "$oldest_snapshot")"
  current="$(jq -r "$jq_path // 0" "$LATEST_FILE")"

  metric_delta "$oldest" "$current"
}

metric_history_values() {
  local jq_path="$1"
  local count="${2:-5}"

  get_recent_snapshots "$count" |
    while read -r snapshot; do
      if jq -e "$jq_path" "$snapshot" >/dev/null 2>&1; then
        jq -r "$jq_path" "$snapshot"
      fi
    done
}

metric_growth_intervals() {
  local jq_path="$1"
  local count="${2:-5}"

  local previous=""
  local current=""

  metric_history_values "$jq_path" "$count" |
    while read -r current; do
      if [[ -n "$previous" ]]; then
        metric_delta "$previous" "$current"
      fi

      previous="$current"
    done
}

metric_snapshot_time_intervals() {
  local count="${1:-5}"

  local previous=""
  local current=""

  get_recent_snapshots "$count" |
    while read -r snapshot; do
      current="$(jq -r '.timestamp // empty' "$snapshot")"

      if [[ -n "$previous" && -n "$current" ]]; then
        local previous_epoch current_epoch
        previous_epoch="$(date -d "$previous" +%s)"
        current_epoch="$(date -d "$current" +%s)"

        metric_delta "$previous_epoch" "$current_epoch"
      fi

      previous="$current"
    done
}

# Statistical Metrics

metric_average() {
  awk '
    { sum += $1; count++ }
    END {
      if (count == 0) {
        print 0
      } else {
        printf "%.0f\n", sum / count
      }
    }
  '
}

metric_min() {
  awk '
    NR == 1 { min = $1 }
    $1 < min { min = $1 }
    END {
      if (NR == 0)
        print 0
      else
        print min
    }
  '
}

metric_max() {
  awk '
    NR == 1 { max = $1 }
    $1 > max { max = $1 }
    END {
      if (NR == 0)
        print 0
      else
        print max
    }
  '
}

metric_count() {
  awk '
    END {
      print NR
    }
  '
}

# Domain Metrics

metric_storage_net_growth() {
  local count="${1:-5}"

  metric_history_delta '.storage.used_bytes' "$count"
}

metric_movie_net_growth() {
  local count="${1:-5}"

  metric_history_delta '.libraries.movies.count' "$count"
}

metric_tv_net_growth() {
  local count="${1:-5}"

  metric_history_delta '.libraries.tv.count' "$count"
}

metric_movie_values() {
  local count="${1:-5}"

  metric_history_values '.libraries.movies.count' "$count"
}

metric_tv_values() {
  local count="${1:-5}"

  metric_history_values '.libraries.tv.count' "$count"
}

metric_movie_trend() {
  metric_trend "$(metric_movie_net_growth "$1")"
}

metric_tv_trend() {
  metric_trend "$(metric_tv_net_growth "$1")"
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
