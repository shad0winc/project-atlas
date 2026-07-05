#!/usr/bin/env bash
set -euo pipefail

ATLAS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARI_DATA_DIR="/mnt/storage/configs/atlas/ari"
MEDIA_ROOT="/mnt/storage/media"
ARI_SNAPSHOT_DIR="$ARI_DATA_DIR/snapshots"
LATEST_FILE="$ARI_DATA_DIR/latest.json"

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

  local safe_timestamp
  safe_timestamp="$(date +"%Y-%m-%dT%H-%M-%S%z")"

  local snapshot_file
  snapshot_file="$ARI_SNAPSHOT_DIR/$safe_timestamp.json"

  local total_media_size
  total_media_size="$(du -sh "$MEDIA_ROOT" 2>/dev/null | awk '{print $1}')"

  local available_storage
  available_storage="$(df -h "$MEDIA_ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"

  local movie_count tv_count anime_movie_count anime_tv_count

  movie_count="$(find "$MEDIA_ROOT/Movies" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
  tv_count="$(find "$MEDIA_ROOT/TV" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
  anime_movie_count="$(find "$MEDIA_ROOT/Anime Movies" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
  anime_tv_count="$(find "$MEDIA_ROOT/Anime TV" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"

  cat > "$snapshot_file" <<EOF
{
  "timestamp": "$timestamp",
  "media_root": "$MEDIA_ROOT",
  "total_media_size": "$total_media_size",
  "available_storage": "$available_storage",
  "libraries": {
    "movies": $movie_count,
    "tv": $tv_count,
    "anime_movies": $anime_movie_count,
    "anime_tv": $anime_tv_count
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
  cat "$LATEST_FILE"
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
