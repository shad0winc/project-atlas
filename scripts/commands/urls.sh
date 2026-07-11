#!/usr/bin/env bash

atlas_command_urls() {
  local env_file="$ATLAS_PROJECT_DIR/.env"

  if [[ ! -f "$env_file" ]]; then
    atlas_fail "Missing environment file: $env_file"
    return 1
  fi

  # shellcheck disable=SC1090
  source "$env_file"

  if [[ -z "${LXC_IP:-}" ]]; then
    atlas_fail "LXC_IP is not configured in $env_file"
    return 1
  fi

  cat <<URLS
Homepage:      http://${LXC_IP}:3000
Jellyfin:      http://${LXC_IP}:8096
Jellyseerr:    http://${LXC_IP}:5055
Sonarr:        http://${LXC_IP}:8989
Sonarr Anime:  http://${LXC_IP}:8990
Radarr:        http://${LXC_IP}:7878
Radarr Anime:  http://${LXC_IP}:7879
Prowlarr:      http://${LXC_IP}:9696
qBittorrent:   http://${LXC_IP}:8080
Bazarr:        http://${LXC_IP}:6767
Maintainerr:   http://${LXC_IP}:6246
Tautulli:      http://${LXC_IP}:8181
Dozzle:        http://${LXC_IP}:9999
Sports Feed:  http://${LXC_IP}:8097
URLS
}
