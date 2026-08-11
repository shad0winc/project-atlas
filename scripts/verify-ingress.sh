#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${ATLAS_PROJECT_DIR:-/opt/project-atlas}"
COMPOSE_FILE="$PROJECT_DIR/stack/ingress.yml"
COMPOSE_PROJECT="atlas-ingress"
RUNTIME_CONFIG_DIR="${ATLAS_RUNTIME_CONFIG_DIR:-/mnt/storage/configs/atlas}"
MAINTENANCE_DIR="${ATLAS_MAINTENANCE_DIR:-$RUNTIME_CONFIG_DIR/maintenance}"
MAINTENANCE_FLAG="$MAINTENANCE_DIR/enabled"

EXPECTED_CADDY_MEMORY=536870912
EXPECTED_CADDY_CPUS=1000000000
EXPECTED_CADDY_PIDS=256

EXPECTED_API_MEMORY=1073741824
EXPECTED_API_CPUS=2000000000
EXPECTED_API_PIDS=512

EXPECTED_PORTAL_MEMORY=1610612736
EXPECTED_PORTAL_CPUS=2000000000
EXPECTED_PORTAL_PIDS=512

passed=0
failed=0

pass() {
  printf 'OK   %s\n' "$1"
  passed=$((passed + 1))
}

fail() {
  printf 'FAIL %s\n' "$1" >&2
  failed=$((failed + 1))
}

check_equal() {
  local description="$1"
  local expected="$2"
  local actual="$3"

  if [[ "$actual" == "$expected" ]]; then
    pass "$description"
  else
    fail "$description (expected=$expected actual=$actual)"
  fi
}

check_command() {
  local description="$1"
  shift

  if "$@" >/dev/null 2>&1; then
    pass "$description"
  else
    fail "$description"
  fi
}

container_value() {
  local container="$1"
  local template="$2"

  docker inspect "$container" \
    --format "$template" \
    2>/dev/null
}

printf '%s\n\n' 'Atlas Ingress Verification'

if [[ -f "$COMPOSE_FILE" ]]; then
  pass "Ingress Compose source present"
else
  fail "Ingress Compose source present"
fi

check_command \
  "Ingress Compose configuration valid" \
  docker compose \
    --env-file "$PROJECT_DIR/.env" \
    -p "$COMPOSE_PROJECT" \
    -f "$COMPOSE_FILE" \
    config --quiet

if docker network inspect atlas-ingress >/dev/null 2>&1; then
  pass "Ingress network present"
else
  fail "Ingress network present"
fi

for container in \
  atlas-caddy \
  atlas-api \
  atlas-portal
do
  if docker inspect "$container" >/dev/null 2>&1; then
    pass "$container container present"
  else
    fail "$container container present"
    continue
  fi

  status="$(
    container_value \
      "$container" \
      '{{.State.Status}}'
  )"

  health="$(
    container_value \
      "$container" \
      '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}'
  )"

  check_equal \
    "$container running" \
    "running" \
    "$status"

  check_equal \
    "$container healthy" \
    "healthy" \
    "$health"
done

check_equal \
  "Caddy memory ceiling" \
  "$EXPECTED_CADDY_MEMORY" \
  "$(
    container_value \
      atlas-caddy \
      '{{.HostConfig.Memory}}'
  )"

check_equal \
  "Caddy CPU ceiling" \
  "$EXPECTED_CADDY_CPUS" \
  "$(
    container_value \
      atlas-caddy \
      '{{.HostConfig.NanoCpus}}'
  )"

check_equal \
  "Caddy PID ceiling" \
  "$EXPECTED_CADDY_PIDS" \
  "$(
    container_value \
      atlas-caddy \
      '{{.HostConfig.PidsLimit}}'
  )"

check_equal \
  "API memory ceiling" \
  "$EXPECTED_API_MEMORY" \
  "$(
    container_value \
      atlas-api \
      '{{.HostConfig.Memory}}'
  )"

check_equal \
  "API CPU ceiling" \
  "$EXPECTED_API_CPUS" \
  "$(
    container_value \
      atlas-api \
      '{{.HostConfig.NanoCpus}}'
  )"

check_equal \
  "API PID ceiling" \
  "$EXPECTED_API_PIDS" \
  "$(
    container_value \
      atlas-api \
      '{{.HostConfig.PidsLimit}}'
  )"

check_equal \
  "Portal memory ceiling" \
  "$EXPECTED_PORTAL_MEMORY" \
  "$(
    container_value \
      atlas-portal \
      '{{.HostConfig.Memory}}'
  )"

check_equal \
  "Portal CPU ceiling" \
  "$EXPECTED_PORTAL_CPUS" \
  "$(
    container_value \
      atlas-portal \
      '{{.HostConfig.NanoCpus}}'
  )"

check_equal \
  "Portal PID ceiling" \
  "$EXPECTED_PORTAL_PIDS" \
  "$(
    container_value \
      atlas-portal \
      '{{.HostConfig.PidsLimit}}'
  )"

check_command \
  "Caddy configuration valid" \
  docker exec \
    atlas-caddy \
    caddy validate \
    --config /etc/caddy/Caddyfile

if [[ -f "$MAINTENANCE_FLAG" ]]; then
  check_command \
    "Caddy maintenance liveness reachable" \
    docker exec \
      atlas-caddy \
      curl \
        --fail \
        --silent \
        --show-error \
        --output /dev/null \
        --resolve atlas.shadowinc.co:443:127.0.0.1 \
        https://atlas.shadowinc.co/_atlas/ingress-health

  check_command \
    "Portal backend reachable during maintenance" \
    docker exec \
      atlas-caddy \
      curl \
        --fail \
        --silent \
        --show-error \
        --output /dev/null \
        http://atlas-portal:3000/

  api_response="$(
    docker exec \
      atlas-caddy \
      curl \
        --fail \
        --silent \
        --show-error \
        http://atlas-api:8000/api/v1/health \
      2>/dev/null ||
      true
  )"

  if printf '%s' "$api_response" | grep -q '"status":"ok"'; then
    pass "API backend reachable during maintenance"
  else
    fail "API backend reachable during maintenance"
  fi

  portal_status="$(
    docker exec atlas-caddy curl \
      --silent \
      --show-error \
      --output /dev/null \
      --write-out '%{http_code}' \
      --resolve atlas.shadowinc.co:443:127.0.0.1 \
      https://atlas.shadowinc.co/ \
      2>/dev/null || true
  )"
  check_equal "Portal public maintenance isolation" "503" "$portal_status"

  api_status="$(
    docker exec atlas-caddy curl \
      --silent \
      --show-error \
      --output /dev/null \
      --write-out '%{http_code}' \
      --resolve atlas.shadowinc.co:443:127.0.0.1 \
      https://atlas.shadowinc.co/api/v1/health \
      2>/dev/null || true
  )"
  check_equal "API public maintenance isolation" "503" "$api_status"
else
  check_command \
    "Portal route reachable through Caddy" \
    docker exec \
      atlas-caddy \
      curl \
        --fail \
        --silent \
        --show-error \
        --output /dev/null \
        --resolve atlas.shadowinc.co:443:127.0.0.1 \
        https://atlas.shadowinc.co/

  api_response="$(
    docker exec \
      atlas-caddy \
      curl \
        --fail \
        --silent \
        --show-error \
        --resolve atlas.shadowinc.co:443:127.0.0.1 \
        https://atlas.shadowinc.co/api/v1/health \
      2>/dev/null ||
      true
  )"

  if printf '%s' "$api_response" | grep -q '"status":"ok"'; then
    pass "API route reachable through Caddy"
  else
    fail "API route reachable through Caddy"
  fi
fi

printf '\nPassed: %s\n' "$passed"
printf 'Failed: %s\n' "$failed"

if (( failed > 0 )); then
  printf '\nAtlas Ingress Status: FAIL\n' >&2
  exit 1
fi

printf '\nAtlas Ingress Status: PASS\n'
