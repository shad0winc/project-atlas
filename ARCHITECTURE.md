# Project Atlas Architecture

> **Simplicity Meets Ingenuity**

---

# Purpose

Project Atlas is an intelligent self-hosted media platform designed to automate media acquisition, organization, delivery, monitoring, and operational decision-making.

Rather than being a collection of Docker containers, Atlas is a modular platform composed of independent subsystems that work together to provide a reliable, observable, and maintainable media environment.

---

# Core Design Principles

Atlas is built around seven engineering principles.

1. Simplicity
2. Reliability
3. Observability
4. Automation
5. Operational Intelligence
6. Recoverability
7. Documentation First

---

# Platform Architecture

```
                          Project Atlas
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
 Media Platform             Atlas CLI          Documentation
        │                        │                        │
        └──────────────┬─────────┘                        │
                       ▼                                  │
          Atlas Retention Intelligence (ARI)             │
                       │                                  │
      ┌────────────┬────────────┬────────────┬────────────┐
      ▼            ▼            ▼            ▼
   Health      Analytics     Forecast   Recommendations
```

---

# Major Subsystems

## 1. Media Platform

Responsible for acquiring, organizing, and serving media.

### Services

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
- Maintainerr
- Homepage
- Dozzle
- Tautulli
- Recyclarr

---

## 2. Atlas CLI

Provides a unified operational interface.

Core commands include:

```
atlas doctor
atlas verify
atlas status
atlas backup
atlas update

atlas ari collect
atlas ari report
```

Future versions will expand the CLI into additional namespaces.

---

## 3. Atlas Retention Intelligence (ARI)

ARI is the operational intelligence layer of Project Atlas.

Instead of merely reporting system state, ARI evaluates platform health, analyzes historical behavior, predicts future resource requirements, and provides operational recommendations.

### Health Engine

Responsible for:

- Docker validation
- VPN validation
- Storage validation
- Library validation
- Health scoring

---

### Analytics Engine

Responsible for:

- Immutable snapshots
- Historical analysis
- Trend detection
- Operational summaries

---

### Forecast Engine

Responsible for:

- Storage forecasting
- Daily growth analysis
- Capacity planning
- Forecast confidence

---

### Recommendation Engine

Responsible for:

- Health recommendations
- Capacity recommendations
- Forecast recommendations

---

## 4. Documentation

Atlas documentation is version controlled alongside the platform.

Documentation includes:

- Architecture
- Charter
- Roadmap
- Build Log
- Changelog
- ADRs
- EDRs
- Maturity Model

Documentation is considered a core subsystem of Atlas.

---

# Media Flow

```
Users
   │
   ▼
Jellyseerr
   │
   ▼
Sonarr / Radarr
   │
   ▼
Prowlarr
   │
   ▼
qBittorrent
   │
   ▼
Media Storage
   │
   ▼
Jellyfin
```

---

# Operational Intelligence Flow

```
Filesystem
Docker
Jellyfin
Configuration
        │
        ▼
ARI Collect
        │
        ▼
Immutable Snapshot
        │
        ▼
Health Engine
        │
        ▼
Analytics Engine
        │
        ▼
Forecast Engine
        │
        ▼
Recommendation Engine
        │
        ▼
Operational Report
```

---

# Network Architecture

```
Internet
     │
     ▼
Gluetun VPN
     │
     ▼
qBittorrent
     │
     ▼
Prowlarr
     │
     ▼
Sonarr / Radarr
     │
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
├── downloads
├── configs
├── backups
└── atlas
    └── ari
        ├── latest.json
        └── snapshots/
```

Snapshots are immutable.

Every collection creates a permanent operational record.

---

# Operational Workflow

Routine platform maintenance:

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

---

# Recovery Workflow

Before making significant changes:

1. Run `atlas doctor`
2. Run `atlas verify`
3. Create a backup
4. Verify the backup
5. Apply the change
6. Verify the platform again

Operational safety always takes priority over convenience.

---

# Architecture Philosophy

Project Atlas follows several architectural rules.

## Single Responsibility

Every subsystem owns one responsibility.

---

## Modular Design

Subsystems communicate through well-defined interfaces.

---

## Shared Configuration

Configuration is centralized.

```
config/atlas.conf
```

---

## Immutable Operational History

Historical operational data is never modified.

Every snapshot becomes a permanent record.

---

## Runtime State

Shared operational values are published once and consumed by dependent subsystems.

This eliminates duplicate calculations while keeping subsystem responsibilities separate.

---

## Documentation as Code

Documentation evolves alongside implementation.

No significant engineering change is considered complete until the documentation has been updated.

---

# Future Platform Evolution

Planned capabilities include:

- Atlas Web Portal
- User Intelligence
- Smart TV Automation
- Sports Integration
- REST API
- Multi-server Atlas
- Plugin Framework
- AI-assisted operational insights
