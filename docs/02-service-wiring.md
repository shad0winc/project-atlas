# Service Wiring

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
