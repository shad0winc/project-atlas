# Restore writer boundary and held failures

Status: source integration, not deployed. Existing format-2/3 live restore blocks
remain in place. This hardens the existing filesystem restore orchestrator before
native Sports and metadata/policy transaction integration.

The exact filesystem-restore writer set is atlas-api, atlas-sports-controller,
atlas-notifications-worker and atlas-sports-writer. The private Sports writer must
be included even while metadata refresh is disabled because it owns state-writing
endpoints. Public maintenance alone does not stop its worker or private API.

Stop consumers first and the private writer last. Each stop uses 35 seconds,
exceeding the metadata worker's 25-second join deadline and matching its Compose
stop allowance. Inspect only Running, Status, ExitCode and OOMKilled. A successful
Docker stop command alone is insufficient: require stopped/exited, no OOM and exit
0 or SIGTERM status 143. Missing/unparseable/running/restarting/killed/error states
fail closed. Recheck the full writer set after shutdown and again after the durable
pre-restore recovery point, immediately before filesystem state application.

Restart in reverse order, with the private writer before its consumers; retain
existing readiness and post-restore checks. No application process is killed
selectively inside Dispatcharr, and no native backend is stopped by this change.
Dispatcharr/Teamarr capture currently requires their containers running; their
future quiescence must be coordinated with native backup/restore preparation.

If application fails and automatic revert is incomplete, do not restart writers
against mixed state. Only a transaction marked reverted plus successful live
consumer validation permits restart under held maintenance. Reverted consumer
validation failure, failed rollback, invalid resume, and invalid abort all keep
writers stopped and retain maintenance/the deployment lock for explicit recovery.
A failure before state mutation retains the existing normal-operation cleanup.

Tests use isolated Docker stubs and temporary transaction fixtures; they do not
stop production containers or alter private state. Real shutdown/restart and native
cross-surface recovery acceptance remain required. This is not proof of atomic
PostgreSQL/JWT/Teamarr/metadata/policy application or crash recovery, and does not
unblock format-2/3 live restore or authorize deployment.
