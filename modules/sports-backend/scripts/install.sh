#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
MODULE_DIR="$PROJECT_DIR/modules/sports-backend"
MODULE_ENV_FILE="$MODULE_DIR/.env"
EXAMPLE_ENV_FILE="$MODULE_DIR/.env.example"
COMPOSE_FILE="$MODULE_DIR/docker-compose.yml"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

test -f "$EXAMPLE_ENV_FILE" ||
    fail "Sports backend .env.example is missing."

if [[ -e "$MODULE_ENV_FILE" && -L "$MODULE_ENV_FILE" ]]; then
    fail "Sports backend .env must not be a symbolic link."
fi

if [[ ! -e "$MODULE_ENV_FILE" ]]; then
    cp "$EXAMPLE_ENV_FILE" "$MODULE_ENV_FILE"
fi

test -f "$MODULE_ENV_FILE" ||
    fail "Sports backend .env must be a regular file."

chmod 600 "$MODULE_ENV_FILE"

install -d -m 750 \
    /mnt/storage/configs/dispatcharr \
    /mnt/storage/configs/teamarr

# Dispatcharr AIO initializes PostgreSQL as PUID/PGID 1000 by default.
# The bind-mounted /data root must therefore be traversable by that identity
# before the container's own initialization scripts can run.
chown 1000:1000 /mnt/storage/configs/dispatcharr

docker compose \
    --env-file "$MODULE_ENV_FILE" \
    -f "$COMPOSE_FILE" \
    pull

docker compose \
    --env-file "$MODULE_ENV_FILE" \
    -f "$COMPOSE_FILE" \
    up -d

for container in atlas-dispatcharr atlas-teamarr; do
    running=false

    for _ in $(seq 1 30); do
        state="$(
            docker inspect \
                --format '{{.State.Status}}' \
                "$container" \
                2>/dev/null || true
        )"

        if [[ "$state" == "running" ]]; then
            running=true
            break
        fi

        sleep 2
    done

    [[ "$running" == true ]] ||
        fail "$container did not reach running state."
done

"$MODULE_DIR/scripts/verify.sh"

echo 'Sports backend installation complete.'
