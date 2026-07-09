# Project Atlas

> **An intelligent self-hosted media platform built for reliability, automation, and operational insight.**

Project Atlas combines a modern media stack with built-in health monitoring, analytics, forecasting, and operational recommendations. Designed to run on a Proxmox Debian LXC, Atlas provides a production-ready platform for managing and serving media to friends and family.

---

# Features

## Media Platform

- Jellyfin Media Server
- Jellyseerr Request Management
- Sonarr (TV)
- Sonarr Anime
- Radarr (Movies)
- Radarr Anime
- Prowlarr Index Management
- Recyclarr Quality Synchronization
- Bazarr Subtitle Management
- Maintainerr Lifecycle Management
- qBittorrent Download Client
- Homepage Dashboard
- Dozzle Log Viewer
- Tautulli Analytics

---

## Atlas Intelligence (ARI)

Atlas Retention Intelligence (ARI) continuously monitors the health and operation of the platform.

### Health Engine

- Platform health scoring
- Docker validation
- VPN validation
- Storage validation
- Jellyfin validation
- Snapshot freshness monitoring

### Analytics Engine

- Immutable operational snapshots
- Historical storage analysis
- Library growth tracking
- Trend analysis
- Operational summaries

### Forecast Engine

- Storage growth forecasting
- Average daily growth
- Capacity forecasting
- Estimated storage exhaustion
- Forecast confidence

### Recommendation Engine

- Health recommendations
- Capacity recommendations
- Forecast recommendations

---

# System Requirements

Recommended:

- Proxmox VE
- Debian LXC
- Intel Quick Sync capable CPU
- Docker Engine
- Docker Compose
- Dedicated media storage
- VPN provider (Windscribe recommended)

---

# Installation

```bash
cd /opt
unzip project-atlas.zip
cd project-atlas

cp .env.example .env
nano .env

./scripts/install.sh
```

Set the LXC IP address in `.env`:

```bash
hostname -I
```

---

# Included Services

| Service | Port |
|---------|-----:|
| Jellyfin | 8096 |
| Jellyseerr | 5055 |
| Sonarr | 8989 |
| Sonarr Anime | 8990* |
| Radarr | 7878 |
| Radarr Anime | 7879* |
| Prowlarr | 9696 |
| qBittorrent | 8080 |
| Bazarr | 6767 |
| Maintainerr | 6246 |
| Tautulli | 8181 |
| Homepage | 3000 |
| Dozzle | 9999 |

\*If configured.

---

# Storage Layout

```
/mnt/storage
├── backups
├── configs
├── downloads
│   ├── complete
│   ├── incomplete
│   ├── movies
│   ├── tv
│   ├── anime-movies
│   └── anime-tv
└── media
    ├── Movies
    ├── TV
    ├── Anime Movies
    └── Anime TV
```

---

# Atlas CLI

Project Atlas includes a unified operational CLI.

Common commands:

```bash
atlas doctor
atlas verify
atlas status
atlas backup
atlas update

atlas ari collect
atlas ari report
```

---

# Documentation

Documentation is located in:

```
docs/
```

Including:

- Architecture
- Build Log
- Changelog
- Maturity Model
- ADRs
- EDRs
- Roadmap

---

# Current Status

**Version:** 1.0.0

**Status:** Production Ready

Current capabilities include:

- Production media platform
- Operational CLI
- Health monitoring
- Historical analytics
- Capacity forecasting
- Operational recommendations

---

# Roadmap

The next major milestones include:

- Atlas Web Portal
- User Intelligence
- Smart TV Automation
- Sports Platform
- REST API

---

# License

Private project for personal, friends, and family use.
