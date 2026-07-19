# Project Atlas Roadmap

Project Atlas is an intelligent, modular, self-hosted entertainment platform built for friends and family.

---

# Guiding Principles

- Simplicity over complexity
- Reliability over novelty
- Observability before automation
- Automation before manual intervention
- Documentation as a first-class feature
- Modular architecture
- User-first experience

---

# Completed Milestones

## M-001 — Platform Foundation ✅

Completed:

- Proxmox LXC deployment
- Docker platform
- Intel Quick Sync
- Storage architecture
- Network configuration
- VPN integration
- Backup system
- Git integration

---

## M-002 — Media Platform ✅

Completed:

- Jellyfin
- Jellyseerr
- Sonarr
- Sonarr Anime
- Radarr
- Radarr Anime
- Prowlarr
- Recyclarr
- Bazarr
- Maintainerr
- Homepage
- Dozzle
- Tautulli
- qBittorrent

---

## M-003 — Atlas CLI ✅

Completed:

- atlas doctor
- atlas verify
- atlas backup
- atlas update
- atlas status
- atlas services
- atlas urls
- atlas git

---

## M-004 — Atlas Retention Intelligence (ARI) ✅

Completed:

### Health Engine

- Docker validation
- VPN validation
- Storage validation
- Library validation
- Snapshot freshness

### Analytics Engine

- Historical snapshots
- Growth analysis
- Trend analysis
- Historical comparisons

### Forecast Engine

- Average growth
- Capacity forecasting
- Estimated full date
- Confidence calculations

### Recommendation Engine

- Health recommendations
- Capacity recommendations
- Forecast recommendations

---

## M-005 — Documentation Platform ✅

Completed:

- README
- CHARTER
- ROADMAP
- BUILD_LOG
- MATURITY
- ARCHITECTURE
- OPERATIONS
- CHANGELOG
- ADR documentation
- EDR documentation
- Release Notes

---

## M-006 — Atlas Module SDK ✅

Completed:

### Module Framework

- Module registry
- Module lifecycle
- Module enable / disable
- Module install / uninstall
- Module update
- Module verification
- Module health

### Module SDK

- Standard module layout
- Module template
- Module scaffolding
- atlas module create
- Self-contained module architecture

### First Module

- Sports module
- Separate Docker container
- Jellyfin integration
- Runtime verification

---

# Active Development

## M-007 — Sports Platform

Goal:

Create an optional sports ecosystem that integrates with Jellyfin while remaining completely modular.

Planned:

- Sports feed management
- Authorized provider integration
- Team favorites
- League favorites
- Sports requests
- Homepage integration
- ARI awareness
- Sports dashboard

---

## M-008 — Atlas Web Portal

Planned:

- Administrator Dashboard
- User Dashboard
- Module Dashboard
- ARI Dashboard
- Forecast Dashboard
- Documentation Portal

---

## M-009 — User Intelligence

Planned:

### Favorites

- Movies
- TV
- Anime
- Sports

### Retention Policies

- Smart retention
- Protected media
- Auto follow
- Next episode
- Request expiration

### User Policies

- Per-user preferences
- Notifications
- Favorites protection

---

## M-010 — Atlas Platform Expansion

Planned:

- REST API
- Plugin framework
- Notification framework
- Mobile integration
- AI services

---

## M-011 — Family Experience

Planned:

- Profiles
- Personalization
- Request history
- Recommendations
- Shared experience

---

## M-012 — Game Server Platform

Planned:

Dedicated game server infrastructure.

Initial targets:

- Minecraft
- Terraria
- Valheim
- Factorio
- Palworld
- ARK
- Rust

Features:

- Server requests
- One-click deployment
- Resource allocation
- Backups
- Updates
- Mod support
- SteamCMD

---

# Long-Term Vision

Project Atlas is no longer simply a media server.

It is a modular, self-hosted entertainment platform built around reusable modules.

Current modules:

- Core Platform
- Sports

Future modules:

- Games
- AI
- Notifications
- Home Automation
- Books
- Music
- Photos

Every module follows the Atlas Module SDK and can be installed, enabled, updated, verified, or removed independently.


---

## M-020 — Family Experience

### M-020.1 — User Identity and Profile Framework

- [x] Jellyfin-linked Atlas profile schema
- [x] Durable user registry and per-user profile storage
- [x] Optional first name, last name, email, and birthday fields
- [x] User role and account status
- [x] User management and verification CLI
- [x] Core profile tests

### M-020.2 — Invitation and Registration

- [x] Identity runtime layout and invitation persistence
- [x] Secure hashed invitation tokens and lifecycle validation
- [ ] Email invitations
- [ ] Shareable invitation links
- [ ] Expiring single-use tokens
- [ ] Registration form
- [ ] Jellyfin account provisioning
- [ ] Invitation revocation and resend
- [ ] Registration audit events
