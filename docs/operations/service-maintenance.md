# Services scans and reviewed Bazarr maintenance

The Services page reads `/mnt/storage/configs/atlas/runtime/services/latest.json`.
Refreshing that file is separate from reading the API report. This worker observes
managed containers and registry manifests, validates the new snapshot with the
running API's Service Lifecycle models, then atomically publishes it. Failed
validation preserves the prior snapshot. Scans do not pull image layers or replace
containers. Registry failures produce unknown update status.

The report preserves observation timestamps. Bazarr preview rejects observations
older than two hours. An older or equal recognized LinuxServer version is not
advertised as an upgrade. Unknown version formats still require review.

## Deployment prerequisites

Deploy the API, Portal and core changes through the existing reviewed Atlas
publication process. Install `tools/operations/atlas_service_maintenance.py` as
`/usr/local/libexec/atlas-service-maintenance/atlas_service_maintenance.py`, owned
by root and not writable by the API user. Install the three companion systemd
units into `/etc/systemd/system` and review their paths before enabling them.
The worker creates private job state under `/var/lib/atlas-service-maintenance`.

The existing root-owned `/run/atlas-maintenance-control` directory must already
be mounted into the API, and its group must allow GID 20000 access. The worker
creates only `services.sock`; it leaves `control.sock` intact. The API runs as
UID 999. The worker accepts root and UID 999 peers and only four fixed operations.
API routes require `global_admin`; browser writes retain the existing CSRF policy.
Do not expose the socket through a public proxy or mount the Docker socket into
the API. The worker needs Docker CLI/buildx and the deployment scheduler lock.

After the matching API image is healthy, start `atlas-service-maintenance.service`,
submit an initial scan with `atlas-service-scan.service`, and confirm its persisted
job completed and the snapshot timestamp and Bazarr identity match live Docker.
Enable `atlas-service-scan.timer` for hourly scans. A busy job coalesces scheduled
submissions. Failed jobs retain a safe error code and the previous report remains
readable. If removing this integration, stop the timer and worker before reverting
the matching API/Portal publication. The prior report is retained privately as
`previous-snapshot.json`.

## Bazarr scope and recovery

The worker bridges the already installed, reviewed ls371 Bazarr transaction only.
It does not prepare or approve arbitrary future updates. It uses the fixed runner
at `/usr/local/libexec/atlas-bazarr-update-ls371/atlas_bazarr_update.py`, its pinned
review authorization, and existing backup/transition journals. Provision that
authorization locally in `/etc/atlas/service-maintenance/bazarr-review.sha256`,
a root-owned mode 0600 regular file containing the already approved review hash.
The authorization is not stored in repository source. That runner remains
the authority for locking, backups, replacement, validation and rollback.

An already completed update offers rollback only while maintenance mode is active,
the retained container and fresh backup remain available, and the runner's saved
publication, maintenance marker, source pins and protected-container context still
match. A later Atlas API/Portal deployment invalidates that original context.
The worker reports `deployment_context_changed` and disables Bazarr changes until
a fresh review authorizes the new context; it never rewrites the original journal
or bypasses the installed runner's guards. Scans and history remain available. Rollback restores
the previous container, configuration and database and retains replaced data
separately. The UI requires reviewing that consequence before submission. If an
interrupted rollback leaves recovery intent, retry invokes the same journaled
rollback rather than creating a new transaction. A worker restart marks its
incomplete job failed; inspect the underlying transaction before retrying.

Maintenance history is populated from completed and rolled-back Bazarr receipts.
A post-operation scan failure does not undo a successful underlying operation;
inspect Bazarr status and retry the scan. General container update preparation,
automatic patching and whole-site backup orchestration remain separate work.
