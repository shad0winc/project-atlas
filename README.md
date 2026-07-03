# Project Atlas

Production media stack for your Proxmox Debian LXC.

## Install

```bash
cd /opt
unzip project-atlas.zip
cd project-atlas
cp .env.example .env
nano .env
./scripts/install.sh
```

Set `LXC_IP` in `.env` to the output of:

```bash
hostname -I
```

## Services

- Jellyfin: 8096
- Sonarr: 8989
- Radarr: 7878
- Prowlarr: 9696
- qBittorrent: 8080
- Jellyseerr: 5055
- Bazarr: 6767
- Maintainerr: 6246
- Tautulli: 8181
- Homepage: 3000
- Dozzle: 9999

## Paths

Host/LXC:

```text
/mnt/storage/downloads
/mnt/storage/media/Movies
/mnt/storage/media/TV
/mnt/storage/configs
/mnt/storage/backups
```

Container paths:

```text
/downloads
/media/Movies
/media/TV
```
