#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${ATLAS_PROJECT_DIR:-/opt/project-atlas}"
MODULE_DIR="$PROJECT_DIR/modules/sports-backend"
COMPOSE_FILE="$MODULE_DIR/docker-compose.yml"
EXAMPLE_ENV="$MODULE_DIR/.env.example"

DISPATCHARR_IMAGE='ghcr.io/dispatcharr/dispatcharr@sha256:e764cd3fb3a4b14e0c96eeb830cce645b44ef0a2494838e21462c71dde5abeb4'
TEAMARR_IMAGE='ghcr.io/pharaoh-labs/teamarr@sha256:d846ec078cde27f68e94f5fc3eec7f1ec29eca11f653b157ac352fef84b73c0c'

fail() {
    printf 'FAIL %s\n' "$*" >&2
    exit 1
}

ok() {
    printf 'OK   %s\n' "$*"
}

for file in \
    module.conf \
    .env.example \
    README.md \
    docker-compose.yml \
    scripts/install.sh \
    scripts/uninstall.sh \
    scripts/update.sh \
    scripts/verify.sh \
    scripts/health.py
do
    test -f "$MODULE_DIR/$file" ||
        fail "Required file missing: $file"
done

grep -Fq "image: $DISPATCHARR_IMAGE" "$COMPOSE_FILE" ||
    fail "Dispatcharr image is not pinned to the approved digest"

grep -Fq "image: $TEAMARR_IMAGE" "$COMPOSE_FILE" ||
    fail "Teamarr image is not pinned to the approved digest"

if grep -Fq ':latest' "$COMPOSE_FILE"; then
    fail "Mutable :latest image tag is prohibited"
fi

if grep -Eq '^[[:space:]]+ports:' "$COMPOSE_FILE"; then
    fail "Sports backend must not publish host ports"
fi

if grep -Eq 'atlas-ingress|atlas-backend' "$COMPOSE_FILE"; then
    fail "Sports backend must not join ingress/backend networks"
fi

grep -Fq 'DISPATCHARR_ENV: "aio"' "$COMPOSE_FILE" ||
    fail "Dispatcharr AIO mode is not explicit"

grep -Fq ':/data' "$COMPOSE_FILE" ||
    fail "Dispatcharr persistent /data mount is missing"

grep -Fq ':/app/data' "$COMPOSE_FILE" ||
    fail "Teamarr persistent /app/data mount is missing"

docker compose \
    --env-file "$EXAMPLE_ENV" \
    -f "$COMPOSE_FILE" \
    config >/dev/null ||
    fail "Sports backend Compose declaration is invalid"

ok "Declarative Sports backend contract valid"
ok "Immutable image digests pinned"
ok "No public host ports declared"
ok "Persistent mounts declared"

dispatcharr_exists=false
teamarr_exists=false

docker inspect atlas-dispatcharr >/dev/null 2>&1 &&
    dispatcharr_exists=true

docker inspect atlas-teamarr >/dev/null 2>&1 &&
    teamarr_exists=true

if [[ "$dispatcharr_exists" != "$teamarr_exists" ]]; then
    fail "Sports backend runtime is partially installed"
fi

if [[ "$dispatcharr_exists" == false ]]; then
    ok "Runtime not installed; declaration-only verification complete"
    exit 0
fi

for path in \
    /mnt/storage/configs/dispatcharr \
    /mnt/storage/configs/teamarr
do
    test -d "$path" ||
        fail "Persistent directory missing: $path"
done

dispatch_uid="$(stat -c '%u' /mnt/storage/configs/dispatcharr)"
dispatch_gid="$(stat -c '%g' /mnt/storage/configs/dispatcharr)"
dispatch_mode="$(stat -c '%a' /mnt/storage/configs/dispatcharr)"

[[ "$dispatch_uid" == "1000" ]] ||
    fail "Dispatcharr state root has unexpected UID: $dispatch_uid"

[[ "$dispatch_gid" == "1000" ]] ||
    fail "Dispatcharr state root has unexpected GID: $dispatch_gid"

# Owner must have rwx. Group/other must not have write permission.
# The pinned image may add execute to /data during startup (for example,
# Atlas-created 0750 becomes 0751), so exact mode equality is inappropriate.
[[ "$dispatch_mode" =~ ^7[0145][0145]$ ]] ||
    fail "Dispatcharr state root has unsafe mode: $dispatch_mode"

teamarr_mode="$(
    stat -c '%a' /mnt/storage/configs/teamarr
)"

[[ "$teamarr_mode" == "750" ]] ||
    fail "Teamarr state root has unexpected mode: $teamarr_mode"

for container in atlas-dispatcharr atlas-teamarr; do
    state="$(
        docker inspect \
            --format '{{.State.Status}}' \
            "$container"
    )"

    [[ "$state" == "running" ]] ||
        fail "$container is not running"

    published="$(
        docker port "$container" 2>/dev/null || true
    )"

    [[ -z "$published" ]] ||
        fail "$container unexpectedly publishes host ports"

    networks="$(
        docker inspect \
            --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' \
            "$container"
    )"

    grep -qw atlas <<<"$networks" ||
        fail "$container is not attached to atlas"

    if grep -Eq 'atlas-ingress|atlas-backend' <<<"$networks"; then
        fail "$container joined a prohibited network"
    fi
done

dispatcharr_config_image="$(
    docker inspect \
        --format '{{.Config.Image}}' \
        atlas-dispatcharr
)"

teamarr_config_image="$(
    docker inspect \
        --format '{{.Config.Image}}' \
        atlas-teamarr
)"

[[ "$dispatcharr_config_image" == "$DISPATCHARR_IMAGE" ]] ||
    fail "Running Dispatcharr container does not use pinned image"

[[ "$teamarr_config_image" == "$TEAMARR_IMAGE" ]] ||
    fail "Running Teamarr container does not use pinned image"

ok "Dispatcharr running on private atlas network"
ok "Teamarr running on private atlas network"
ok "No host ports published"
ok "Runtime image references match approved digests"
ok "Persistent-directory permission contract satisfied"
