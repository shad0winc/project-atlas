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

# Operations Intelligence Foundation

Project Atlas now includes a provider-neutral Operations collection
foundation for read-only host and Docker inspection.

## Implemented Components

- `OperationsCollector`
- `SystemCollector`
- `HostSystemProvider`
- `DockerCommandRunner`
- `DockerProvider`
- `DockerEngineSnapshot`
- `DockerContainerSummary`
- `DockerContainerSnapshot`
- `DockerMountSnapshot`
- `DockerNetworkSnapshot`
- `DockerPortSnapshot`

## Read-Only System Collection

The System collector reports:

- hostname;
- operating system;
- kernel;
- uptime;
- logical CPU count and model;
- total, used, and available memory.

Run a direct development verification with:

    python - <<'PY'
    from atlas.operations.collectors import SystemCollector

    section = SystemCollector().collect_checked()
    print(section.to_dict())
    PY

## Read-Only Docker Collection

The Docker provider supports:

- Docker client and server identity;
- daemon capacity and container counts;
- deterministic container inventory;
- container state and health;
- restart and OOM state;
- lifecycle timestamps normalized to UTC;
- memory, CPU, and PID ceilings;
- restart policies;
- mounts;
- network attachments and aliases;
- exposed and published ports.

Run a direct development verification with:

    python - <<'PY'
    from atlas.operations.collectors import DockerProvider

    provider = DockerProvider()

    print(provider.engine().to_dict())

    for container in provider.containers():
        print(container.to_dict())
    PY

Inspect one container with:

    python - <<'PY'
    from atlas.operations.collectors import DockerProvider

    snapshot = DockerProvider().container("atlas-api")
    print(snapshot.to_dict())
    PY

All collection and provider operations are read-only. They do not
start, stop, restart, remove, or otherwise mutate containers.

## Current Architectural Boundary

This milestone does not yet provide:

- the final Docker `OperationsCollector`;
- multi-collector `OperationsReport` orchestration;
- `atlas operations` CLI commands;
- API routes;
- Portal dashboards;
- scheduler integration;
- daily-report integration;
- event publication or notifications.

These consumers will be added above the normalized collector and
provider contracts in later increments.

---

# Atlas Operations Reports

Atlas Operations provides one read-only report covering the current
host and Docker deployment.

## Commands

```bash
atlas operations
atlas operations help
atlas operations report
atlas operations report --json
atlas operations report --report-id nightly-operations
```

Every report includes its identity, hostname, Atlas version, Git
commit, UTC generation timestamp, status, score, summary, attention
references, and normalized sections.

## System section

The System section reports hostname, operating system, kernel, uptime,
CPU, and memory.

## Containers section

The Containers section reports Docker Engine availability, inventory,
runtime state, health checks, restart thresholds, OOM state, stopped-
container exit state, and resource-governance compliance.

## Status markers

- `[OK]` — Healthy
- `[!]` — Warning
- `[X]` — Critical
- `[?]` — Unknown

Reports end with an **Attention Required** summary.

## Failure isolation

A failed collector does not abort the complete report. Atlas emits an
unknown fallback section and preserves successfully collected
sections.

## JSON contract

`atlas operations report --json` is the canonical machine-readable
contract. Consumers should not parse the human renderer.

## Current boundaries

The subsystem remains read-only and does not yet persist history,
schedule reports, publish events, send notifications, expose API
routes, or perform automatic remediation.

# Production Ingress Operations

## Verify Ingress Governance

```bash
scripts/verify-ingress.sh
```

The verifier checks:

- ingress Compose syntax and network availability;
- Caddy, Atlas API, and Atlas Portal health;
- production memory, CPU, and PID ceilings;
- Caddy configuration;
- Portal and API routing through local HTTPS ingress.

Expected result:

```text
Atlas Ingress Status: PASS
```

| Service | Memory | CPU | PID limit |
| --- | ---: | ---: | ---: |
| Caddy | 512 MiB | 1 CPU | 256 |
| Atlas API | 1 GiB | 2 CPUs | 512 |
| Atlas Portal | 1.5 GiB | 2 CPUs | 512 |

These limits do not constrain Jellyfin, FFmpeg, Intel GPU
transcoding, media playback, or the broader media stack.

Run this verifier after ingress deployment or configuration changes
and before production release validation.

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
