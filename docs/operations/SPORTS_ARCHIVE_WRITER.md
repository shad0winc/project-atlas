# Sports writer startup against archive-restored metadata

This is isolated acceptance after SPORTS_ARCHIVE_METADATA.md, not a live restore
implementation or deployment. All prior native/five-surface/archive/maintenance
acceptance remains required. Media browse work stays queued after Sports in
V1_MEDIA_BROWSE_ACCEPTANCE.md.

## Runtime and packaging

Use the installed writer runtime by immutable image ID
sha256:a352324695a2bff4b838313a8fd6f81445384f641ce7a1e9f016a8d00a55b0dd.
Do not pull, build, retag or replace any image. A fresh UUID-labelled disposable
container runs the image's actual default command, python3 /srv/sports/private_api.py,
without an entrypoint override. It runs explicitly as UID/GID1000 with no additional
groups or capabilities, no new privileges, read-only root filesystem, private IPC,
network none, no published ports, restart no, bounded memory/PIDs/CPU, disabled Docker
healthcheck, no logging driver and a small /tmp tmpfs. Only container loopback HTTP
is queried from a subprocess inside the disposable container.

The installed image supplies Python and its runtime. Reviewed current writer source
is mounted read-only over /srv/sports: exactly the COPY inputs declared by the actual
Dockerfile.private-api, including provider modules, shared-admission config shim and
disabled policy example. Source inputs and the Dockerfile are pinned by the entry
point. This tests current application code in the installed writer runtime; it does
not claim the deployed image already embeds that code or prove a new production
image build. No package installation or Internet access is required.

The source copy is private to this fixture. Inside the container it is readable by
UID1000 and read-only. The four normal startup registries use a new UID1000-owned
/state directory. No production state, canary, provider credentials or configuration
is mounted. The bearer token is a fixed synthetic fixture value.

## Restored-data acceptance

The unchanged five-surface sequence extracts metadata and policy from the very same
archive used for native database/JWT recovery. The inherited archive receipts and
semantic checks must pass first. During each restored verification phase, create
fresh copies of the restored metadata and policy for the disposable writer:

- /metadata: UID/GID1000, directory0700, files0600, writable bind.
- /policy: root:GID1000, directory0750, refresh.json0640, read-only bind.
- /state: empty UID/GID1000 directory0700, writable bind for normal startup.
- /srv/sports: reviewed source, read-only bind.

No policy is enabled or rewritten. The real writer initializes its normal registries,
loads the disabled refresh policy and starts its actual HTTP server. A bounded
in-container Python probe checks effective/real/saved numeric identities, group list,
metadata/policy ownership and modes, immutable SQLite quick_check, restored attempts,
alias count, cooldown/cache fields, policy parsing and matching raw file hashes.
The inherited full metadata checks validate complete aliases and budget/cache/policy
before and after this container acceptance.

HTTP checks require unauthenticated /health success, missing/wrong bearer refusal on
the metadata status endpoint, authenticated status exactly disabled/not running and
an authenticated metadata query returning unavailable while policy is disabled.
The unavailable result is intentional; it must not become an empty successful result.
This does not test enabled broker HTTP requests, external cache refresh or provider
request charging. No external network is available.

Stop normally with SIGTERM and require exit0/PID0/no OOM. Restart the same container,
repeat the data/HTTP probe and prove all startup registry bytes persist unchanged.
Stop normally again. Source, restored metadata and policy copies must remain unchanged,
and the original recovery journal bytes must match their pre-container digests.
This acceptance runs twice through the inherited verification hook: before restored
native app startup and after native persistence restart. Thus private maintenance
release remains dependent on actual writer acceptance in both phases.

Container inspection requires full owned ID, derived name, immutable image, label,
command/user/security/network settings and exact private bind sources/read-write
modes. Mount array ordering has no significance; every actual mount is checked.
Cleanup stops/removes only the exact revalidated owned container, verifies its label
has no remaining containers, then removes private copies. Docker daemon failures
are not interpreted as empty results. No prune, force removal or production restart.
All prior production identity/full normalized mount and deployment pointer guards apply.

## Verification and limits

Run git diff --check, the full tests/core pytest suite and
scripts/diagnostics/sports-archive-writer-drill.py before committing. This entry point
requires the exact precommit canonical HEAD; do not blindly rerun it after commit.
Follow RC1-first CI/merge, identical main CI/merge and canonical fast-forward only.
Do not deploy as part of this gate.

Local tests exercise exact packaging, actual unmodified writer subprocess startup,
authenticated HTTP/disabled policy behavior, normal SIGTERM/restart and registry
persistence, plus container identity/mount/security refusal cases. Local app tests use
the host identity and an ephemeral loopback port; they are not Docker or numeric
UID1000 acceptance. The full mapped-UID/container/native sequence must pass on CT100.

This tests read/serve startup and shutdown with disabled refresh, not native metadata
writes through the writer, provider enrollment or enabled request accounting. Writable
registry fixtures are freshly initialized, not archive-restored sixteen-surface state.
Actual four-service operational quiescence, full image/deployment integration, production
health preflight, ingress, coherent production backup and sixteen-surface restore remain
separate gates. Native PostgreSQL restoration still needs compatible cold-cluster
roles/configuration. Existing archive scaffolds, detached capture/import and synthetic
provider data limitations remain. Live restore stays disabled and production unchanged.
