# Backup

The canonical operator entry point is the Atlas CLI:

```bash
atlas backup
```

Add an operator note when useful:

```bash
atlas backup --notes "before maintenance"
```

List completed Atlas backups with:

```bash
atlas backup --list
```

Production Atlas backups are stored beneath the configured
`ATLAS_BACKUP_DIR`, currently `/mnt/storage/backups/atlas`.

## Contents

The Atlas backup command captures the repository-managed configuration and
recovery material defined by the backup command, including Compose files,
configuration, documentation, modules, scripts, version metadata, and a
`BACKUP_INFO.txt` manifest.

Atlas configuration backups do not contain the Media library itself.

## Storage-Safe Publication

Atlas does not write a new backup directly to its final success name.

The archive is first created in the backup directory as:

```text
atlas-<timestamp>.tar.gz.partial
```

Before creation, Atlas reports the backup filesystem's currently available
capacity. This is observability, not deletion authorization and not a promise
that a particular archive will fit.

The temporary archive must be created successfully and pass `tar` validation
before it is atomically renamed to:

```text
atlas-<timestamp>.tar.gz
```

If creation, validation, or publication fails, the operation returns failure,
the partial artifact is removed when safe, and the canonical completed-backup
name is not published.

`atlas backup --list` and backup retention consider only canonical
`atlas-*.tar.gz` artifacts. Partial files never participate in normal success
reporting or retention selection.

## Retention

The current Atlas backup command keeps the newest 10 canonical Atlas backups.
Storage pressure does not authorize automatic deletion outside this explicit
backup-retention behavior.

## Validation Status

M-023.22 verified the backup failure boundary with temporary test data and
simulated archive/publication failures. Read-only production inspection found
10 canonical Atlas backups, zero `.partial` artifacts, and successfully
validated the newest canonical archive and its `BACKUP_INFO.txt` manifest.

Production storage was not filled and no production backup was created or
deleted during M-023.22 validation.

Full state-by-state backup verification and restore testing remain separate
v1.0 Backup and Recovery roadmap work; this document does not mark those
unfinished tasks complete.
