#!/usr/bin/env bash

atlas_health_json_escape() {
  python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

atlas_health_result() {
  local status="$1"
  local name="$2"
  local category="$3"
  local message="${4:-}"

  case "$status" in
    healthy|warning|critical|unknown)
      ;;
    *)
      echo "Invalid health status: $status" >&2
      return 1
      ;;
  esac

  printf '{"name":%s,"category":%s,"status":%s,"message":%s,"details":{}}\n' \
    "$(atlas_health_json_escape "$name")" \
    "$(atlas_health_json_escape "$category")" \
    "$(atlas_health_json_escape "$status")" \
    "$(atlas_health_json_escape "$message")"
}

health_ok() {
  atlas_health_result "healthy" "$@"
}

health_warn() {
  atlas_health_result "warning" "$@"
}

health_fail() {
  atlas_health_result "critical" "$@"
}

health_unknown() {
  atlas_health_result "unknown" "$@"
}
