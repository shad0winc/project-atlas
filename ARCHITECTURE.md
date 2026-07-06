# Project Atlas Architecture

> **Simplicity Meets Ingenuity**

---

# Purpose

Project Atlas is a modular, Docker-based media platform designed to automate media acquisition, organization, delivery, validation, and operational intelligence while remaining simple to operate.

Atlas intentionally favors a small number of well-integrated services over a large collection of loosely maintained containers. Every subsystem has a clearly defined responsibility and contributes to a reliable, maintainable, and recoverable platform.

---

# Design Principles

Atlas is built around several core engineering principles.

1. Simplicity
2. Reliability
3. Operational Intelligence
4. Recoverability
5. Documentation First
6. Version Controlled Infrastructure
7. Immutable Operational History

---

# High-Level Architecture

```
                        Users
                           │
                           ▼
                     Jellyseerr
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
      Sonarr                          Radarr
          │                                 │
          ▼                                 ▼
  Sonarr Anime                    Radarr Anime
          │                                 │
          └──────────────┬──────────────────┘
                         ▼
                     Prowlarr
                         │
                         ▼
                    qBittorrent
                         │
                         ▼
                   Media Storage
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
          Jellyfin            Maintainerr
              │
              ▼
 Atlas Retention Intelligence (ARI)
              │
              ▼
 Validation • Analysis • Reporting
```

---

# System Components

## Media Platform

Responsible for acquiring, organizing, managing, and serving media.

Core components:

- Jellyfin
- Jellyseerr
- Sonarr
- Sonarr Anime
- Radarr
- Radarr Anime
- Prowlarr
- qBittorrent
- Gluetun
- Bazarr
- Tautulli
- Maintainerr
- Homepage
- Dozzle

Supporting components:

- Recyclarr

Future components:

- Readarr
- Audiobookshelf
- Komga
- Kavita
- FlareSolverr

---

## Operational CLI

Atlas includes an operational command-line interface that standardizes platform administration.

Core commands include:

- `atlas doctor`
- `atlas verify`
- `atlas backup`
- `atlas restore`
- `atlas update`
- `atlas git`
- `atlas ari collect`
- `atlas ari report`

The CLI provides a consistent operational experience for routine maintenance and system validation.

---

## Atlas Retention Intelligence (ARI)

Atlas Retention Intelligence (ARI) is the operational intelligence subsystem of Project Atlas.

ARI continuously captures, validates, compares, and summarizes the operational state of the platform.

Current responsibilities include:

- Collect platform metadata
- Collect filesystem state
- Collect Jellyfin metadata
- Preserve immutable historical snapshots
- Validate media libraries
- Validate library paths
- Compare historical snapshots
- Detect operational changes
- Generate operational reports

Future responsibilities include:

- Growth analysis
- Capacity forecasting
- Health scoring
- Configuration drift detection
- Automated recommendations

---

# Media Platform

## Core Services

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

## Manual Services

Executed only when needed.

- Recyclarr

---

## Future Services

Optional functionality.

- Readarr
- Audiobookshelf
- Komga
- Kavita
- FlareSolverr

---

# Network Architecture

```
Internet
        │
        ▼
+----------------------+
|     Gluetun VPN      |
+----------------------+
           │
           ▼
+----------------------+
|    qBittorrent       |
+----------------------+
           │
           ▼
+----------------------+
|      Prowlarr        |
+----------------------+
      │           │
      ▼           ▼
 Sonarr       Radarr
      │           │
      ▼           ▼
 Anime       Anime
      │           │
      └──────┬────┘
             ▼
       Jellyseerr
             │
             ▼
        Jellyfin
```

---

# Storage Layout

```
/mnt/storage
├── media
│   ├── Movies
│   ├── TV
│   ├── Anime Movies
│   └── Anime TV
│
├── downloads
│
├── configs
│
├── backups
│
└── atlas
    └── ari
        ├── latest.json
        └── snapshots/
```

---

# Snapshot Lifecycle

```
atlas ari collect
        │
        ▼
Collect platform state
        │
        ▼
Normalize collected data
        │
        ▼
Generate immutable snapshot
        │
        ▼
Update latest.json
        │
        ▼
Archive historical snapshot
```

Historical snapshots are never modified.

Every execution creates a new immutable record of platform state.

---

# Data Flow

```
Filesystem
        │
Docker
        │
Jellyfin
        │
Configuration
───────────────
        │
        ▼
ARI Collectors
        │
        ▼
Snapshot
        │
        ▼
Validation
        │
        ▼
Analysis
        │
        ▼
Operational Report
```

---

# Operational Lifecycle

Routine operational workflow:

```
atlas doctor
        │
        ▼
atlas verify
        │
        ▼
atlas ari collect
        │
        ▼
atlas ari report
        │
        ▼
atlas backup
        │
        ▼
atlas update
```

This workflow ensures the platform remains validated before administrative changes are performed.

---

# Recovery Strategy

Before every significant change:

1. Run `atlas doctor`
2. Run `atlas verify`
3. Create a backup (`atlas backup`)
4. Verify the backup
5. Perform the change
6. Run `atlas verify` again

Operational safety always takes precedence over convenience.

---

# Release Strategy

```
Development
      │
      ▼
Feature Implementation
      │
      ▼
Validation
      │
      ▼
Documentation
      │
      ▼
Git Commit
      │
      ▼
GitHub Push
      │
      ▼
Release Tag
```

Every feature is expected to include:

- Documentation
- Validation
- Operational testing
- Version control

---

# Architecture Philosophy

Project Atlas follows several architectural principles.

## Single Responsibility

Each component performs one primary function.

---

## Shared Configuration

Configuration exists in one location.

```
config/atlas.conf
```

---

## Immutable History

Historical operational data is never modified.

Every operational change produces a new snapshot.

---

## Raw Data First

Machine-readable values are stored alongside formatted values.

Example:

```
used
used_bytes
```

Human-readable reports never replace machine-readable data.

---

## Human-Friendly Operations

Humans read reports.

Machines read JSON.

Both are treated as first-class outputs.

---

## Documentation as Code

Documentation evolves alongside implementation.

Architectural decisions, engineering decisions, and operational procedures are version controlled with the project.

---

# Future Expansion

Planned platform evolution includes:

- Historical trend analysis
- Storage growth forecasting
- Capacity planning
- Configuration drift detection
- Health scoring
- Automated reporting
- Scheduled ARI collection
- Recommendation engine
- Atlas Management Portal
- REST API
- Multi-server Atlas deployments
- Gaming server management
- Plugin architecture
- AI-assisted operational insights
- High availability
