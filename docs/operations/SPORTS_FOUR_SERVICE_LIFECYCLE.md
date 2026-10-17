# Actual four application processes inside the native capture fence

This gate follows SPORTS_ARCHIVE_REFRESH.md. It replaces the four disposable
SQLite-counter proxies at the native capture boundary with the actual API,
Sports controller, notifications worker and Sports private writer applications.
The inherited same-archive native/metadata recovery, writer authentication,
broker, bounded refresh-child shutdown and maintenance acceptance still run.
The sixteen-surface archive fixture is not a sixteen-application operational
restore. No production deployment, production stop/start or live restore occurs.

## Reviewed source and installed runtime contract

The source export at canonical `6a46f68885b6196e8b1f16671f2bf0f9539066bb`
contained 567 committed files; ZIP SHA256
`e27112623bc8d5e1bc44e2d13d70a02b101f74c694302059b6be322f72bf2c73`.
It supplied the notifications source absent from the earlier partial export.
Environment files were excluded. The 2026-10-17 read-only CT100 inventory found
all four production containers running/healthy with no observed ID, image, PID,
start time, restart count, full configuration or normalized-mount changes. Docker
health is not a substitute for the separate release doctor/preflight.

The helper pins the four installed image IDs and verifies their exact default
commands, null entrypoints and absence of image-declared volumes before use.
No image is built or pulled. Staged reviewed source is mounted read-only at the
real application paths; it retains the operator's ownership, preserves executable
processor/shell files and is readable by the application users. API code overlays
both /srv/atlas and /srv/apps/api/atlas_api. Controller and notifications use the
source tree at /opt/project-atlas; the private writer retains its reviewed flat
Dockerfile COPY layout. A synthetic atlas.conf supplies only fixture roots and
disabled cleanup. No production .env or configuration file is copied.

UUID names, exact full IDs, image IDs, label, default commands, user, workdir,
fixture environment, supplementary groups, complete bind records and security
settings are validated before control and cleanup. API runs as numeric999:999
with groups20000/20001; the other workers run1000:1000, with group20000 for
controller and notifications. The writer has no additional group. Shared event
access uses the private group20000 file, not production identity directories.
All containers have network none, no published ports, no Docker socket, read-only
rootfs, cap-drop ALL, no-new-privileges, restart no, log none, private IPC, bounded
CPU/memory/PIDs and a bounded /tmp tmpfs. Image healthchecks are disabled: bounded
explicit application probes provide the acceptance evidence.

## Application behavior and safe limits

The API uses its real uvicorn command and FastAPI startup, a synthetic JWT secret,
and a private requests directory; the local health endpoint must respond. This
is startup/lifecycle evidence, not authenticated acquisition, playback, provider
or identity-directory integration acceptance.

The controller runs its real worker.py with an empty TheSportsDB key and no
external provider enabled. Its real no-provider path writes a heartbeat. The
fixture does not replace run_cycle, but it also does not claim a successful
provider discovery/recording/Live-TV pipeline. After restart its heartbeat must
advance. The separate controlled metadata broker and refresh gates retain their
loopback-only provider acceptance.

The notifications worker runs its real shell entry point, common config/event
libraries, subscriber pipeline, Python processor/router and local JSON log. No
Discord or webhook destination is configured. Event1 must be recorded exactly
once and the real subscriber cursor must advance to1 before quiescence. While
all four applications are stopped, the operator appends synthetic event2. It
must remain pending until restart. Resumed acceptance requires cursor2 and an
ordered log containing exactly events1 and2. This is cursor persistence without
replay across a clean restart, not a claim of exactly-once remote delivery under
arbitrary crashes or partially delivered batches.

The private writer runs its actual default command with a synthetic bearer token
and four private registry paths. Its health endpoint must respond. Archived
metadata authentication, disabled-policy, controlled broker and refresh behavior
remain covered by the inherited additional writer gates, not inferred from health.

## Shutdown changes

Before this candidate, controller main had no explicit SIGTERM handler and used
an uninterruptible polling sleep; the notifications shell had no stop trap. A
container PID1 lifecycle cannot rely on ordinary default signal behavior.

Controller main now installs TERM/INT handlers that set a stop Event, finishes
an already admitted cycle and refuses another, interrupts its idle wait, returns0
and restores previous handlers. Existing --once returns the cycle result. A
blocking provider/recording operation is not forcibly cancelled by this change;
production stop deadlines still depend on its bounded work and require separate
in-flight acceptance where applicable.

The notifications shell trap requests stop and interrupts/reaps only its own
idle sleep child. An active subscriber pipeline completes through the existing
success/failure cursor logic before exit; no independent cursor advancement is
added. A stop between checking the flag and starting sleep is rechecked so the
worker cannot enter a fresh long sleep after stop. An unbounded active delivery
batch is not made bounded by this change. This gate uses local disabled delivery
and tests prompt idle stop, actual processing and persistent cursor restart.

## Capture, exclusion, restart and cleanup

The existing real restore.sh helpers run through the private fence controller.
Only the writer-name adapter maps the four names to exact owned fixture IDs; the
stop order, 35-second grace, quiesced recheck, reverse start and readiness wait
remain the real shell implementation. Private execution exclusion and maintenance
ownership stay held across capture and resumed application acceptance.

All four must be exited0/PID0/no OOM before a bounded private data-tree snapshot
is copied. Its bytes/modes are compared; source data and copied snapshot must
remain unchanged throughout the inherited native baseline capture callback.
This private tree copy is acceptance evidence, not a new archive/restore API.
Only after capture and recheck is event2 appended, while all services remain
stopped and cursor1 is confirmed. Reverse restart begins with the private writer.
Application probes, notification progress and unchanged captured/source copies
must pass before private maintenance release.

Cleanup revalidates the owned contract, stops normally with35-second grace,
requires exit0/no OOM, removes only the exact fixture IDs without force and checks
that no job-labelled container remains. Production container identity, configuration
and full normalized mounts are compared before/after without printing environment
values. A failed refusal retains failure status; it must never become success by
pruning, forced removal, accepting SIGKILL, or treating Docker errors as no fixtures.

## Verification and remaining gates

Local tests exercise actual host controller TERM handling during idle and admitted
cycle work, and real notifications processor/cursor/restart with fixed paths
redirected into a temporary source tree. Guard tests reject host networking, wrong
UID, command/env changes, production mount sources, extra mounts and published
ports; source ownership, modes and snapshot path checks are covered. Host tests do
not prove mapped Docker identities or availability of the pinned installed images.

On CT100 run the new tests explicitly as UID1000, all core tests, then
scripts/diagnostics/sports-four-service-lifecycle-drill.py as the root operator.
Do not deploy. Follow frozen-file review, RC1-first CI/merge, identical main
CI/merge and canonical ff-only synchronization. V1_SPORTS_RECOVERY_PROGRESS.md
records the preceding accepted history and must distinguish this candidate's
pending CT/CI evidence from completed checkpoints.

Still separate: actual service behavior with enabled providers/remote delivery,
production image build and mount rollout, full sixteen-surface operational restore,
partial setup/import handling, coherent production backup, ingress and doctor,
compatible cold-cluster role/config provisioning, and remaining Sports user flows.
Media browse acceptance remains queued after Sports.
