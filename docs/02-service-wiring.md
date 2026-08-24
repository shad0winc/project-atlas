# Service Wiring — Supplemental Reference

This document preserves service-specific wiring values for the current media
stack. It is a supplemental configuration reference, not a complete installation,
upgrade, rollback, restore, or troubleshooting procedure.

For production procedures, use:

- `docs/guides/INSTALLATION_GUIDE.md`
- `docs/guides/UPGRADE_GUIDE.md`
- `docs/guides/ROLLBACK_GUIDE.md`
- `docs/guides/BACKUP_RESTORE_GUIDE.md`
- `docs/guides/TROUBLESHOOTING_GUIDE.md`

Validate these service values against the deployed environment and
`docs/CONFIGURATION.md` before applying changes. If this reference conflicts with
a canonical v1 guide, stop and follow the canonical guide.

## qBittorrent

Default save path:

```text
/downloads/complete
```

Incomplete path:

```text
/downloads/incomplete
```

Categories:

```text
movies -> /downloads/movies
tv     -> /downloads/tv
```

## Sonarr

Root folder:

```text
/media/TV
```

Download client:

```text
Host: qbittorrent
Port: 8080
Category: tv
```

Enable hardlinks.

## Radarr

Root folder:

```text
/media/Movies
```

Download client:

```text
Host: qbittorrent
Port: 8080
Category: movies
```

Enable hardlinks.

## Prowlarr Apps

Sonarr:

```text
Prowlarr server: http://prowlarr:9696
Sonarr server: http://sonarr:8989
```

Radarr:

```text
Prowlarr server: http://prowlarr:9696
Radarr server: http://radarr:7878
```

## Jellyfin

Libraries:

```text
Movies: /media/Movies
TV: /media/TV
```

Enable Intel Quick Sync / VAAPI with `/dev/dri/renderD128`.

## Jellyseerr

Use internal URLs:

```text
Jellyfin: http://jellyfin:8096
Sonarr: http://sonarr:8989
Radarr: http://radarr:7878
```
