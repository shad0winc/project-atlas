# Project Atlas Handbook

> Operational Guide for Project Atlas

---

# Philosophy

Atlas is designed to be:

- Simple
- Reliable
- Recoverable
- Version Controlled
- Easy to Operate

Every operational task should be executable through the Atlas CLI whenever possible.

---

# Daily Operations

## Check Platform Health

```bash
atlas doctor
atlas verify
```

Review:

- Docker
- Storage
- VPN
- Core services
- Project documentation

---

## View Git Status

```bash
atlas git
```

The preferred state is:

```
nothing to commit, working tree clean
```

---

# Before Making Changes

Always create a backup.

```bash
atlas backup --notes "Reason for backup"
```

Examples:

```bash
atlas backup --notes "Before upgrading Jellyfin"
atlas backup --notes "Before changing VPN provider"
atlas backup --notes "Before Docker update"
```

---

# Updating Atlas

Run:

```bash
atlas update
```

Atlas will:

- Pull updated containers
- Recreate containers
- Clean unused images
- Run Atlas Doctor
- Run Atlas Verify

---

# Viewing Existing Backups

```bash
atlas backup --list
```

---

# Recovery Workflow

Before restoring:

1. Stop Docker containers
2. Verify backup integrity
3. Restore configuration
4. Start Atlas
5. Run

```bash
atlas verify
```

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

Run only when required.

- Recyclarr

---

## Advanced

Optional functionality.

- Unpackerr

---

# Operational Principles

Never:

- Modify production without a backup.
- Leave Git in a dirty state.
- Skip verification after updates.

Always:

- Backup first.
- Verify after changes.
- Commit frequently.
- Push to GitHub.
- Keep documentation current.

---

# Atlas Workflow

Daily

atlas doctor

↓

atlas verify

↓

atlas git

Before Changes

atlas backup

↓

Make Changes

↓

atlas verify

↓

git commit

↓

git push

---

# Long-Term Maintenance

Review:

- Docker updates
- VPN health
- Backup rotation
- Documentation
- GitHub releases

Regular maintenance keeps Atlas reliable.
