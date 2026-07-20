# Project Atlas Administrator Guide

> **Simplicity Meets Ingenuity**

---

# Purpose

The Administrator Guide defines the standard operating procedures for Project Atlas.

It serves as the primary reference for installing, maintaining, validating, updating, and recovering the platform.

Atlas is designed so that routine administration follows a predictable workflow backed by operational validation and historical intelligence.

---

# Administration Philosophy

Atlas follows several operational principles.

- Validate before changing.
- Backup before updating.
- Verify after every change.
- Preserve operational history.
- Automate repetitive tasks.
- Keep documentation synchronized with implementation.

Operational safety is always preferred over convenience.

---

# Daily Operations

The recommended daily workflow is:

```text
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
atlas git
```

This sequence confirms:

- Docker health
- Container status
- VPN connectivity
- Storage availability
- Platform integrity
- Operational state
- Git repository status

---

# Weekly Maintenance

Recommended weekly tasks:

- Review ARI operational reports.
- Review storage utilization.
- Verify VPN connectivity.
- Confirm all containers are healthy.
- Review Docker logs.
- Ensure the Git repository is clean.
- Verify backups are completing successfully.

---

# Monthly Maintenance

Recommended monthly tasks:

- Update Docker images.
- Review documentation.
- Review roadmap progress.
- Validate recovery procedures.
- Remove unused Docker images.
- Review storage growth.
- Archive completed milestones.

---

# Atlas Command-Line Interface

Atlas provides a unified command-line interface for administration.

| Command | Purpose |
|----------|---------|
| `atlas doctor` | Perform platform health checks |
| `atlas verify` | Validate infrastructure and services |
| `atlas ari collect` | Capture an operational snapshot |
| `atlas ari report` | Generate an operational report |
| `atlas backup` | Create a system backup |
| `atlas restore` | Restore from backup |
| `atlas update` | Update Atlas components |
| `atlas git` | Display repository status |

---

# Atlas Retention Intelligence (ARI)

Atlas Retention Intelligence (ARI) is the operational intelligence subsystem of Project Atlas.

ARI continuously records the operational state of the platform by creating immutable snapshots.

Every collection captures information about:

- Platform metadata
- Storage utilization
- Filesystem inventory
- Jellyfin server information
- Jellyfin libraries
- Jellyfin users
- Jellyfin media counts
- Library validation
- Library synchronization

Snapshots are stored under:

```text
/mnt/storage/configs/atlas/ari/
```

Historical snapshots are never modified.

Each execution creates a new record of platform state.

---

# Reading ARI Reports

A standard report includes:

- Platform information
- Storage metrics
- Jellyfin status
- Library inventory
- User inventory
- Validation results
- Synchronization status
- Historical comparisons
- Operational summaries

ARI should be reviewed after:

- Software updates
- Library changes
- Hardware upgrades
- Recovery operations
- Major maintenance

---

# Backup Procedure

Before making significant changes:

1. Run `atlas doctor`
2. Run `atlas verify`
3. Create a backup using `atlas backup`
4. Verify the backup completed successfully
5. Proceed with maintenance

---

# Recovery Procedure

If recovery is required:

1. Restore the latest verified backup.
2. Confirm storage mounts.
3. Start Docker services.
4. Run `atlas verify`.
5. Run `atlas ari collect`.
6. Run `atlas ari report`.

Recovery is complete only after the platform verifies successfully.

---

# Updating Atlas

Before updating:

```text
atlas doctor

atlas verify

atlas backup
```

After updating:

```text
atlas verify

atlas ari collect

atlas ari report

atlas git
```

Every update should conclude with validation and a fresh operational snapshot.

---

# Troubleshooting

## Docker

Run:

```bash
atlas doctor
```

---

## Infrastructure

Run:

```bash
atlas verify
```

---

## Operational State

Run:

```bash
atlas ari report
```

---

## Repository Status

Run:

```bash
atlas git
```

---

# Operational Best Practices

Always:

- Validate before making changes.
- Backup before updating.
- Review ARI reports after significant changes.
- Keep documentation current.
- Commit changes frequently.
- Push validated work to GitHub.

Never:

- Modify production without a verified backup.
- Ignore validation failures.
- Edit ARI snapshots manually.
- Leave the Git repository in an unknown state.

---

# References

Additional documentation:

- `ARCHITECTURE.md`
- `CHARTER.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `docs/BUILD_LOG.md`
- `docs/MATURITY.md`
- `docs/ADR/`
- `docs/EDR/`
