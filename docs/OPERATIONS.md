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

Atlas Operations provides read-only live reporting and immutable report
persistence for the current host and Docker deployment.

## Commands

```bash
atlas operations
atlas operations help
atlas operations report
atlas operations report --json
atlas operations report --report-id nightly-operations
atlas operations save
atlas operations save --json
atlas operations save --report-id nightly-operations
atlas operations latest
atlas operations latest --json
atlas operations history
atlas operations history --json
atlas operations history --limit 10
atlas operations compare
atlas operations compare --json
atlas operations compare --include-unchanged
atlas scheduler sync
atlas scheduler inspect operations.collect
atlas scheduler run operations.collect
atlas scheduler history --limit 10
```

## Command behavior

- `report` collects and renders a live report without persisting it.
- `save` collects a live report, writes an immutable history snapshot,
  and atomically updates `latest.json`.
- `latest` loads and validates the most recently persisted report without
  executing collectors.
- `history` loads validated snapshots in newest-first order without
  modifying persisted files.
- `history --limit LIMIT` restricts the maximum returned report count.
- `compare` compares the two newest persisted reports without modifying
  either snapshot or `latest.json`.
- `compare --include-unchanged` includes stable findings in the serialized
  comparison contract while human output remains difference-focused.
- `scheduler sync` registers the core `operations.collect` task together
  with jobs from enabled module manifests.
- `scheduler inspect operations.collect` shows the persistent task state,
  cadence, callback, due status, health, and run counters.
- `scheduler run operations.collect` forces one scheduled collection and
  records the result in scheduler history.

## Scheduled collection

Atlas Operations uses the shared `TaskScheduler`; it does not implement a
second scheduler. The canonical task definition is:

```text
Name:        operations.collect
Interval:    3600 seconds
Callback:    python3 -m atlas.operations_scheduled_collection
Description: Persist an Atlas Operations report
Module:      none
```

An unqualified `atlas scheduler sync` registers core jobs and enabled
module jobs. A targeted command such as `atlas scheduler sync sports`
continues to synchronize only that module and does not register core jobs.

Registration is idempotent. Repeated synchronization refreshes the task
definition while preserving runtime fields such as `run_count`,
`failure_count`, `last_success`, `last_duration_ms`, status, and execution
history.

Operations is a core subsystem, not an optional module. Its scheduler task
therefore stores `module: null`, preventing the optional-module event
publisher from attempting to route Operations events through the module
registry.

The callback performs one direct collection and persistence cycle:

```text
TaskScheduler
      |
      v
atlas.operations_scheduled_collection
      |
      v
OperationsService.collect()
      |
      v
FileOperationsRepository.save()
      |
      +--> history/<generated-at>.json
      `--> latest.json
```

The scheduler executes the callback as a subprocess from the Atlas project
directory. A successful run updates task health, counters, success time,
duration, and scheduler history. Callback failures are normalized through
the existing scheduler execution contract.

## Production Scheduler dispatcher

The shared `TaskScheduler` owns task definitions, individual
`interval_seconds`, due-state calculation, runtime locking, callback execution,
health/counters, and execution history. It remains the sole Atlas scheduler.

Production uses a repository-owned systemd dispatcher to provide recurring
opportunities for the existing scheduler to evaluate due work:

```text
atlas-scheduler.timer
        |
        | every 1 minute
        v
atlas-scheduler.service
        |
        | Type=oneshot
        v
/bin/atlas scheduler run
        |
        v
TaskScheduler.run_due_tasks()
```

The tracked units are:

- `systemd/atlas-scheduler.service`;
- `systemd/atlas-scheduler.timer`.

The service runs from `/opt/project-atlas` and invokes the public Atlas CLI.
It does not run a daemon loop, implement task-specific cadence, maintain a
second scheduler state file, or bypass the Scheduler runtime lock.

The timer uses a one-minute dispatch opportunity:

- `OnBootSec=1min`;
- `OnUnitActiveSec=1min`;
- `Persistent=true`.

The one-minute systemd cadence is intentionally shorter than the shortest
registered Atlas task interval. It bounds dispatch delay without encoding
`operations.collect`, `sports.maintenance`, `sustained-use.sample`, module, or
other task intervals in systemd. Atlas still decides whether each task is due.

The dispatcher process exit contract is:

- exit `0` when no work is due;
- exit `0` when all due callbacks succeed;
- exit `1` when any due callback fails;
- exit `3` when the Scheduler runtime lock prevents execution.

The systemd service does not mask these nonzero Atlas exit statuses. Operators
should therefore treat a failed `atlas-scheduler.service` invocation as a
Scheduler execution signal that requires inspection rather than silently
restarting a second scheduler.

Repository tracking alone does not install or enable these units. Host
installation, `daemon-reload`, enablement, start, and live recurring-dispatch
verification are controlled production deployment steps.

Manual commands such as `atlas scheduler run <task>` remain supported for
explicit operator actions, but they are not the production recurrence
mechanism.

## Scheduled collection repository root

The callback uses `/mnt/storage/configs/atlas/operations` by default.
`ATLAS_OPERATIONS_DIRECTORY` may override that root for automated tests,
isolated deployments, or controlled alternate runtime layouts.

The value is trimmed before use. An empty or whitespace-only override is
rejected rather than silently falling back to the production directory.

## Storage layout

```text
/mnt/storage/configs/atlas/operations/
├── latest.json
└── history/
    └── <generated-at>.json
```

Historical snapshots are immutable. Atlas rejects a second save using the
same generated timestamp instead of replacing the existing snapshot.

`latest.json` is updated only after the historical snapshot is written
successfully.

## History output

Human history output is intentionally concise. Each entry includes the
report identity, generation timestamp, normalized status, and score.

JSON history output uses a stable wrapped collection contract:

    {
      "count": 1,
      "reports": [
        { ...complete OperationsReport contract... }
      ]
    }

Reports are returned newest first. Each JSON entry is the same complete,
validated report contract exposed by `report --json` and `latest --json`.

## Report comparison

`atlas operations compare` retrieves the two newest validated reports from
the repository. The newest report is treated as the current state and the
second-newest report is treated as the previous state.

The comparison service detects:

- added findings;
- removed findings;
- changed findings;
- optionally unchanged findings;
- overall status changes;
- score deltas;
- attention-count deltas.

A finding that moves between sections is represented as one removal from
the previous section and one addition to the current section.

Human output shows report identities, timestamps, status and score changes,
summary counts, and difference details. Unchanged findings are omitted from
human output even when included in the comparison contract.

JSON output contains four top-level fields:

    {
      "previous": { ...OperationsReport... },
      "current": { ...OperationsReport... },
      "summary": { ...derived comparison totals... },
      "changes": [ ...OperationsFindingChange values... ]
    }

Comparison is deterministic and strictly read-only. It does not write new
snapshots, update `latest.json`, or mutate either source report.

## Report contract

Every report includes its schema version, identity, hostname, Atlas version,
Git commit, UTC generation timestamp, status, score, summary, attention
references, and normalized sections.

Stored reports are reconstructed through:

- `OperationFinding.from_dict()`;
- `OperationsSection.from_dict()`;
- `OperationsReport.from_dict()`.

Canonical fields are validated and normalized. Derived fields such as
status, score, summary, counts, and attention references are recomputed
rather than trusted from disk.

## System section

The System section reports hostname, operating system, kernel, uptime, CPU,
and memory.

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
unknown fallback section and preserves successfully collected sections.

Repository read failures, invalid JSON, invalid schema versions, and invalid
domain contracts are normalized into Operations repository errors.

## JSON contract

`atlas operations report --json`, `save --json`, and `latest --json` expose
the canonical machine-readable contract. Consumers should not parse the
human renderer.

## Shared API Contract Foundation

Operations now shares a transport-neutral contract layer located under
`atlas/api`.

The shared package provides:

- canonical API and schema version identifiers;
- immutable success and failure response envelopes;
- normalized API error contracts;
- deterministic JSON-compatible serialization;
- UTC timestamp normalization;
- explicit public exports.

These contracts remain framework-independent and intentionally avoid
FastAPI, Pydantic, Starlette, routing objects, HTTP request objects,
and status codes.

Future Operations HTTP routes will construct shared Atlas API contracts
first and adapt them into FastAPI schemas only at the outer HTTP
boundary.

This preserves one canonical transport contract for:

- CLI output;
- HTTP endpoints;
- automation;
- integration tests;
- future Portal communication.

Existing CLI behavior is unchanged.

Operations HTTP routes remain planned work and are not yet implemented.

## Current boundaries

API routes, notifications, Portal visualization, comparison retention,
and automatic remediation remain planned extensions.

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

## Retiring an incomplete sustained-use certification attempt

An incomplete Q.6 certification attempt must not be deleted, manually rewritten as `failed`, or cleared by moving `session.json` by hand.

Use the explicit retirement path:

```bash
atlas sustained-use status --json

atlas sustained-use abort \
  --confirm-run-id <exact-current-run-id>
```

The confirmation must exactly match the current session run ID. No force bypass exists.

A successful abort transitions the session to `aborted`, records its UTC completion time, and archives the run under:

```text
/mnt/storage/configs/atlas/sustained-use/archive/<run-id>/
```

The archive preserves `session.json`, `latest.json`, and the complete `history/` directory. Atlas moves `session.json` last so an interrupted archive retains the terminal lifecycle boundary and can be retried safely.

After archival, verify the historical run before starting another certification:

```bash
find /mnt/storage/configs/atlas/sustained-use/archive/<run-id> \
  -maxdepth 2 \
  -type f \
  -print

cat /mnt/storage/configs/atlas/sustained-use/archive/<run-id>/session.json
```

The archived session must report `status` as `aborted`. Keep the archive as historical release evidence.

Start a new T0 only after the repaired candidate is clean and published, `sustained-use.sample` is restored at its canonical cadence, and autonomous Scheduler dispatch has been reverified.

## Q.6 fixed-cadence sustained-use operation

Q.6 uses two distinct timing contracts.

The **certification cadence** is fixed at 15 minutes / 900 seconds. Required observation times are derived from T0:

```text
sample 1   = T0
sample 2   = T0 + 900 seconds
sample 3   = T0 + 1800 seconds
...
sample 193 = T0 + 172800 seconds
```

The **Scheduler polling cadence** is 60 seconds. The shorter polling interval does not change the Q.6 observation frequency. It only gives Atlas repeated opportunities to recognize the next fixed certification slot without accumulating Scheduler completion-time drift.

The scheduled callback behavior is:

```text
before fixed slot        -> successful not_due no-op
0..180 seconds late      -> capture one real sample
more than 180 seconds    -> missed-slot hard failure
no active session        -> successful no-op
terminal session         -> successful no-op
history complete         -> successful no-op
```

A missed slot must never be repaired by backfilling multiple observations. Historical samples must represent real observations collected near their required temporal boundaries.

During a real Q.6 run, inspect:

```bash
atlas sustained-use status --json
atlas scheduler inspect sustained-use.sample
atlas health --compact
```

The live Scheduler task should report:

```text
name:              sustained-use.sample
interval_seconds:  60
enabled:           true
status:            healthy
failure_count:     0
```

The `60` second value is the polling interval, **not** the Q.6 certification sample interval.

If a scheduled callback reports a missed-slot failure, preserve the active evidence and treat the certification attempt as release-blocking. Do not manually create replacement samples and do not restart the Q.6 clock until the failure is investigated and the incomplete run is explicitly retired.

Finalization independently validates every persisted observation against its T0-derived slot. Therefore a history with 193 chronologically ordered samples can still fail Q.6 if those observations violate the fixed cadence.

The archived run `q6-20260817T232028Z` is the canonical production example of this distinction: Atlas and the Scheduler remained operationally healthy, but cumulative temporal drift made the run invalid for the exact 48-hour / 193-sample certification contract.

## Q.6 Runtime Bus terminal convergence

The final sustained-use decision must not require the Notifications subscriber cursor to equal the live Runtime Bus journal tail at one instantaneous read. Runtime Bus publication and subscriber consumption are asynchronous, so a healthy subscriber can be briefly behind at the exact sample-193 boundary.

Q.6 freezes the terminal target from the Runtime Bus journal tail recorded by sample 193. Finalization then observes subscriber progress for a bounded 180-second window.

The terminal contract is:

```text
target = sample_193.runtime_bus.journal_tail

cursor >= target within 180 seconds -> terminal PASS
cursor < target while time remains  -> pending, not success
cursor < target after timeout       -> hard failure
```

Events published after sample 193 do not move the frozen target. The live journal may therefore continue to grow while Notifications converges through the certification target.

Operators must not edit the final sample, advance the cursor manually, rewrite the failed session, or retry historical finalization merely to manufacture a pass. Preserve the original terminal record as evidence.

When investigating terminal convergence, inspect the sustained-use finalization output together with current Runtime Bus journal/cursor and Notifications heartbeat evidence. A healthy current subscriber that has consumed through the frozen target demonstrates convergence; it does not alter the historical sample evidence.

A production run may transition to `completed` only after hard evaluation, temporal history evaluation, fixed-slot evaluation, and bounded terminal convergence all pass. `pending` is never equivalent to success, and terminal timeout remains release-blocking.

## Q.6 completed-certification boundary

A successful Q.6 certification ends with a durable `completed` session and a frozen Scheduler boundary.

The certified production sequence is:

1. verify exactly `193/193` persisted samples and zero fixed-slot violations;
2. wait for any in-flight `atlas-scheduler.service` invocation to finish;
3. stop `atlas-scheduler.timer` without disabling it;
4. verify the one-shot Scheduler service is inactive;
5. finalize once through the bounded Runtime Bus terminal observer;
6. require terminal status `passed`;
7. verify the persisted session is `completed`;
8. verify the 193 history samples were not rewritten; and
9. reconcile the result into release documentation before changing release gates.

The final successful v1.0 Q.6 run is `q6-20260822T011449Z` against commit `13a48a5ce1a6e4c5f335f4ae6cd19ba61149fefa`.

Its terminal target was frozen at Runtime Bus journal line `7053`. Notifications converged through that target with final cursor `7068` in two probes. The live journal reached `7070`; that post-target growth is valid and does not change the frozen certification target.

After successful certification, `atlas-scheduler.timer` is expected to be:

```text
enabled: yes
active:  no
```

Do not restart the timer merely to make the post-certification state look active. Any later Scheduler activation belongs to the next explicitly controlled operational or release step.

Historical failed and aborted Q.6 runs remain immutable evidence and must not be rewritten to match the successful run.
