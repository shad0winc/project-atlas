# Project Atlas Release History

> Engineering history of Project Atlas

---

# Versioning

Atlas follows Semantic Versioning.

MAJOR.MINOR.PATCH

Examples:

- 1.0.0
- 1.1.0
- 1.1.1

---

# v0.5.0 — Foundation Release

Release Date:
2026-07-05

Status:
Current

---

## Vision

Transform Atlas from a Docker media stack into an operational platform.

---

## Major Features

### Infrastructure

- Docker Compose architecture
- GitHub integration
- SSH authentication
- Intel GPU acceleration
- VPN isolation

---

### Media Platform

- Jellyfin
- Jellyseerr
- Prowlarr
- Sonarr
- Sonarr Anime
- Radarr
- Radarr Anime
- qBittorrent

---

### Media Intelligence

- Recyclarr
- Quality Profiles
- Custom Formats
- Anime support

---

### Atlas CLI

Introduced:

- atlas doctor
- atlas verify
- atlas update
- atlas backup
- atlas backup --notes
- atlas backup --list
- atlas urls
- atlas version
- atlas git

---

### Architecture

Established:

Core Profile

Manual Profile

Advanced Profile

---

### Documentation

Added:

- CHARTER.md
- ROADMAP.md
- CHANGELOG.md
- BUILD_LOG.md
- MATURITY.md
- INDEXERS.md
- ARCHITECTURE.md
- HANDBOOK.md

---

## Architectural Decisions

### Unpackerr

Moved to the Advanced profile.

Reason:

Public indexers rarely require archive extraction.

Keeping Unpackerr optional simplifies the default deployment.

---

### Recyclarr

Configured as Manual.

Reason:

Quality profile synchronization should occur only when intentionally updating media intelligence.

---

### Backup Strategy

Atlas backups now include:

- Timestamp
- Git branch
- Version
- Operator notes

Automatic retention keeps the newest 10 backups.

---

## Lessons Learned

This release established the operational philosophy of Atlas:

- Keep the platform simple.
- Automate repetitive tasks.
- Document every architectural decision.
- Prefer reliability over feature count.

---

## Next Milestone

M-008

Goals:

- Atlas Restore
- GitHub Release automation
- Status dashboard
- Architecture diagrams
- Operational metrics

---

End of Release
