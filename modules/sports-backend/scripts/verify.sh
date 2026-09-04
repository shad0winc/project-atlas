#!/usr/bin/env bash
set -euo pipefail

project_dir="${ATLAS_PROJECT_DIR:-/opt/project-atlas}"
module_dir="$project_dir/modules/sports-backend"

compose_file="$module_dir/docker-compose.yml"
example_env="$module_dir/.env.example"

fail() {
    printf 'FAIL %s\n' "$*" >&2
    exit 1
}

ok() {
    printf 'OK   %s\n' "$*"
}

test -f "$compose_file" ||
    fail "Sports backend compose file missing"

test -f "$example_env" ||
    fail "Sports backend environment example missing"

grep -Fq 'atlas-dispatcharr:' "$compose_file" ||
    fail "Dispatcharr service declaration missing"

grep -Fq 'atlas-teamarr:' "$compose_file" ||
    fail "Teamarr service declaration missing"

grep -Fq 'DISPATCHARR_ENV: "aio"' "$compose_file" ||
    fail "Dispatcharr must explicitly use AIO deployment mode"

grep -Fq 'ghcr.io/dispatcharr/dispatcharr:latest' "$compose_file" ||
    fail "Dispatcharr image contract is missing"

grep -Fq 'ghcr.io/pharaoh-labs/teamarr:latest' "$compose_file" ||
    fail "Teamarr image contract is missing"

grep -Fq ':/data' "$compose_file" ||
    fail "Dispatcharr /data persistence mount is missing"

grep -Fq ':/app/data' "$compose_file" ||
    fail "Teamarr /app/data persistence mount is missing"

if grep -Eq '^[[:space:]]+ports:' "$compose_file"; then
    fail "Sports backend must not publish host ports"
fi

if grep -Eq 'atlas-ingress|atlas-backend' "$compose_file"; then
    fail "Sports backend must not join Atlas ingress/backend networks"
fi

grep -Fq 'no-new-privileges:true' "$compose_file" ||
    fail "Sports backend services must use no-new-privileges"

grep -Fq '/mnt/storage/configs/dispatcharr' "$example_env" ||
    fail "Dispatcharr persistent-state contract missing"

grep -Fq '/mnt/storage/configs/teamarr' "$example_env" ||
    fail "Teamarr persistent-state contract missing"

ok "Sports backend declaration is structurally valid"
ok "No public host ports are declared"
ok "No Atlas ingress network is joined"
ok "Persistent state roots are declared"
