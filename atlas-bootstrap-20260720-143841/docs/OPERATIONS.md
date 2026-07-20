# Project Atlas Operations Guide

> **Operational Runbook for Project Atlas**

This document describes the standard operating procedures for administering, maintaining, troubleshooting, and updating Project Atlas.

---

# Daily Operations

## Check Platform Health

```bash
atlas doctor
```

Purpose:

- Verify Docker is running
- Verify storage is mounted
- Verify VPN connectivity
- Verify project files
- Verify container health

Expected Result:

```
Overall platform healthy
```

---

## Verify Platform Integrity

```bash
atlas verify
```

Purpose:

- Validate infrastructure
- Validate required services
- Validate storage paths
- Validate VPN
- Validate project files

Run:

- Before upgrades
- After upgrades
- Before backups
- After restores

---

## Generate Operational Snapshot

```bash
atlas ari collect
```

Purpose:

Collect an immutable snapshot of the current platform state.

This command should be executed:

- Before major changes
- After major changes
- Daily (future automation)

---

## Review Operational Report

```bash
atlas ari report
```

Purpose:

Review:

- Platform health
- Historical growth
- Forecast
- Recommendations
- Operational trends

---

# Weekly Maintenance

Recommended tasks:

- Review ARI report
- Review storage growth
- Verify backup completion
- Review container logs
- Update containers if appropriate

Suggested commands:

```bash
atlas doctor
atlas verify
atlas ari collect
atlas ari report
docker compose pull
docker compose up -d
```

---

# Monthly Maintenance

Recommended tasks:

- Review storage forecasts
- Verify disaster recovery procedures
- Validate backups
- Review media quality profiles
- Update documentation if architecture changes

---

# Backup Procedure

Create a backup:

```bash
atlas backup
```

Recommended before:

- Docker updates
- Configuration changes
- Adding services
- System upgrades

After backup:

```bash
atlas verify
```

Confirm the platform remains healthy.

---

# Update Procedure

## Step 1

Verify platform health.

```bash
atlas doctor
atlas verify
```

---

## Step 2

Create backup.

```bash
atlas backup
```

---

## Step 3

Update Atlas.

```bash
atlas update
```

---

## Step 4

Verify platform.

```bash
atlas verify
```

---

## Step 5

Collect a new ARI snapshot.

```bash
atlas ari collect
atlas ari report
```

---

# Recovery Procedure

If an update fails:

1. Stop changes immediately.
2. Review logs.
3. Restore backup.
4. Run:

```bash
atlas verify
atlas doctor
```

5. Confirm ARI health.

---

# Standard Operational Workflow

Routine maintenance:

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
atlas backup
        │
        ▼
atlas update
        │
        ▼
atlas verify
```

---

# Health Monitoring

ARI evaluates:

## Platform

- Docker
- VPN
- Storage
- Snapshot freshness

## Media

- Jellyfin libraries
- Library paths
- Library synchronization

## Intelligence

- Historical analysis
- Capacity forecasting
- Operational recommendations

---

# Troubleshooting

## Docker Issues

```bash
atlas doctor
docker ps
docker compose logs
```

---

## VPN Issues

Verify:

```bash
docker logs gluetun
```

Confirm VPN IP:

```bash
atlas doctor
```

---

## Jellyfin Issues

Verify:

- Libraries exist
- Paths are correct
- Synchronization passes

Run:

```bash
atlas ari report
```

---

## Storage Issues

Check:

```bash
df -h
```

Then:

```bash
atlas verify
```

Review forecast:

```bash
atlas ari report
```

---

# Operational Philosophy

Every operational change should follow this order:

1. Observe
2. Verify
3. Backup
4. Change
5. Validate
6. Document

Operational safety always takes precedence over speed.

---

# Scheduled Automation (Future)

Planned automation:

Daily

- ARI collection
- Health report

Weekly

- Forecast review
- Backup verification

Monthly

- Capacity planning
- Disaster recovery validation

---

# Incident Response Checklist

When unexpected behavior occurs:

- [ ] Run `atlas doctor`
- [ ] Run `atlas verify`
- [ ] Review `atlas ari report`
- [ ] Review Docker logs
- [ ] Verify storage
- [ ] Verify VPN
- [ ] Restore backup if necessary
- [ ] Document findings

---

# Administrator Checklist

Before ending any maintenance session:

- [ ] Platform healthy
- [ ] Verification passed
- [ ] Backup completed
- [ ] ARI snapshot collected
- [ ] Documentation updated (if required)
- [ ] Git committed (if required)

Project Atlas is considered operational only when these checks are complete.


               OBSERVE
                  │
                  ▼
              VERIFY
                  │
                  ▼
              BACKUP
                  │
                  ▼
               CHANGE
                  │
                  ▼
              VALIDATE
                  │
                  ▼
             DOCUMENT
                  │
                  ▼
               COMMIT
