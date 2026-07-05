#!/usr/bin/env bash
set -euo pipefail

ATLAS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ATLAS_CONFIG_FILE="$ATLAS_ROOT/config/atlas.conf"

if [[ ! -f "$ATLAS_CONFIG_FILE" ]]; then
  echo "Missing Atlas config: $ATLAS_CONFIG_FILE"
  exit 1
fi

source "$ATLAS_CONFIG_FILE"

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
  "Libraries",
  "---------",
  "Movies:        \(.libraries.movies.count)",
  "TV:            \(.libraries.tv.count)",
  "Anime Movies:  \(.libraries.anime_movies.count)",
  "Anime TV:      \(.libraries.anime_tv.count)"
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
