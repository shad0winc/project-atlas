# Atlas Docker Networks

Project Atlas uses three named Docker bridge networks.

## atlas-ingress

Purpose:

- Public reverse-proxy traffic
- Communication between Caddy and explicitly published web applications

Expected members:

- Caddy
- Atlas Portal
- Public documentation service
- Public status service
- Jellyfin when public media access is enabled
- Jellyseerr when public request access is enabled

## atlas-backend

Purpose:

- Private application-to-application communication
- Atlas API and internal service integrations

This network must not publish ports directly to the internet.

## atlas-management

Purpose:

- Monitoring
- Diagnostics
- Operational tooling
- Administrative service communication

Administrative interfaces should remain reachable only from trusted local
networks or an approved authenticated access layer.

## Exposure Policy

Only the ingress service may publish TCP ports 80 and 443.

Services such as Sonarr, Radarr, Prowlarr, qBittorrent, Dozzle, and internal
administrative endpoints must never be exposed directly to the public
internet.
