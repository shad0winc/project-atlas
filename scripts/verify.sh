#!/usr/bin/env bash
set -euo pipefail
echo "=== Docker ==="
docker --version
docker compose version
echo
echo "=== Containers ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo
echo "=== Storage ==="
ls -ld /mnt/storage || true
df -h /mnt/storage || true
echo
echo "=== Intel GPU ==="
ls -la /dev/dri || true
