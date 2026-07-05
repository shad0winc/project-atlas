# Project Atlas Architecture

> Simplicity Meets Ingenuity

---

# Purpose

Project Atlas is a modular, Docker-based media platform focused on reliability,
maintainability, operational simplicity, and recoverability.

Atlas intentionally favors a small number of well-integrated services over a
large collection of loosely maintained containers.

---

# Design Principles

1. Simplicity
2. Reliability
3. Automation
4. Recoverability
5. Documentation First
6. Version Controlled Infrastructure

---

# Service Profiles

## Core

Always running.

- Jellyfin
- Jellyseerr
- Prowlarr
- Sonarr
- Sonarr Anime
- Radarr
- Radarr Anime
- qBittorrent
- Gluetun
- Homepage
- Bazarr
- Tautulli
- Maintainerr
- Dozzle

---

## Manual

Executed only when needed.

- Recyclarr

---

## Advanced

Optional functionality.

- Unpackerr
- FlareSolverr (future)

---

# Network Architecture

Internet
        │
        ▼
+----------------+
|   Gluetun VPN  |
+----------------+
        │
        ▼
+----------------+
| qBittorrent    |
+----------------+
        │
        ▼
+----------------+
| Prowlarr       |
+----------------+
        │
 ┌──────┴─────────┐
 ▼                ▼
Sonarr        Radarr
 ▼                ▼
Anime         Anime
 ▼                ▼
+----------------+
| Jellyseerr     |
+----------------+
        │
        ▼
+----------------+
| Jellyfin       |
+----------------+

---

# Storage Layout

/mnt/storage

/media

- Movies
- TV
- Anime Movies
- Anime TV

/downloads

/configs

/backups

---

# Operational Lifecycle

Daily

atlas doctor

↓

atlas verify

↓

atlas backup

↓

atlas update

---

# Recovery Strategy

Before every significant change:

1. atlas backup
2. Verify backup
3. atlas update
4. atlas verify

---

# Release Strategy

Development

↓

Feature Branch

↓

Testing

↓

Merge into main

↓

GitHub Release

---

# Future Expansion

Potential future services:

- Readarr
- Audiobookshelf
- Komga
- Kavita
- FlareSolverr
- Private Tracker Integration
