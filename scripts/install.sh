#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env

set -a
source .env
set +a

mkdir -p "$DOWNLOADS"/{complete,incomplete,movies,tv}
mkdir -p "$MEDIA"/{Movies,TV}
mkdir -p "$CONFIG"/{jellyfin,jellyfin-cache,sonarr,radarr,prowlarr,qbittorrent,jellyseerr,bazarr,maintainerr,tautulli,homepage,recyclarr}
mkdir -p "$BACKUPS"

touch "$CONFIG/homepage"/{settings.yaml,services.yaml,widgets.yaml,bookmarks.yaml,docker.yaml,kubernetes.yaml}

cat > "$CONFIG/homepage/settings.yaml" <<EOF
title: Project Atlas
theme: dark
color: slate
layout:
  Media:
    style: row
    columns: 4
EOF

cat > "$CONFIG/homepage/services.yaml" <<EOF
- Media:
    - Jellyfin:
        href: http://${LXC_IP}:8096
        description: Media server
    - Jellyseerr:
        href: http://${LXC_IP}:5055
        description: Requests
    - Sonarr:
        href: http://${LXC_IP}:8989
        description: TV automation
    - Radarr:
        href: http://${LXC_IP}:7878
        description: Movie automation
    - Prowlarr:
        href: http://${LXC_IP}:9696
        description: Indexers
    - qBittorrent:
        href: http://${LXC_IP}:8080
        description: Downloads
    - Bazarr:
        href: http://${LXC_IP}:6767
        description: Subtitles
    - Maintainerr:
        href: http://${LXC_IP}:6246
        description: Cleanup automation
    - Tautulli:
        href: http://${LXC_IP}:8181
        description: Watch stats
    - Dozzle:
        href: http://${LXC_IP}:9999
        description: Docker logs
EOF

cat > "$CONFIG/homepage/widgets.yaml" <<EOF
- resources:
    cpu: true
    memory: true
    disk: /
EOF

echo "[]" > "$CONFIG/homepage/bookmarks.yaml"
echo "{}" > "$CONFIG/homepage/docker.yaml"
echo "{}" > "$CONFIG/homepage/kubernetes.yaml"

chown -R "${PUID}:${PGID}" "$DATA_DIR"
chmod -R u+rwX,g+rwX "$DATA_DIR"

docker compose pull
docker compose up -d

echo "Project Atlas deployed."
echo "Homepage: http://${LXC_IP}:3000"
