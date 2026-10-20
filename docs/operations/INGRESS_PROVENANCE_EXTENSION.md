# Ingress provenance schema 2

Schema 1 retains the original bounded Sports contract. Existing candidates,
component recipe identities and historical recovery evidence are not rewritten.
Schema 2 adds explicit maintenance Ingress provenance to that base ledger.

The manifest-covered supplements are `ingress-runtime-extension.json`,
`ingress-application-source.tar.gz`, `ingress-application-tracked.json`,
`ingress-api-build.Dockerfile`, `ingress-portal-build.Dockerfile`,
`maintenance-authority.service` and `ingress-release-gate.json`. Three metadata
markers select schema 2; `ingress_extension_commit` and `ingress_extension_tree`
pin its source identity. The source claim is
`verified-base-recipes-plus-linked-service-and-maintenance-repairs`.

Offline `record` validation checks the unchanged base ledger, archive commit,
tracked blobs and executable bits, and reconstructed Git tree. API and Portal
image IDs must match `images.tsv`; retained Dockerfiles may change only FROM
references to digest pins. Caddy binds select read-only subdirectories of an
immutable generation. The retained authority unit equals its archived source
with two source locations pinned and Python safe-path mode added. Release
evidence must consistently bind the successful main push run and all six jobs
to the released commit and tree. Offline checks validate evidence consistency;
collection still requires authenticated remote CI observation.

Read-only schema-2 `live` validation additionally checks:

- The full immutable source generation through directory file descriptors with
  no-follow opens, stable file identities, exact coverage and streamed hashes.
  Production directories must be root-owned mode 0555; files root-owned mode
  0444 or 0555 according to Git executable bits. Hardlinks and symlinks refuse.
- API, Portal and Caddy image IDs, healthy running state, default startup,
  unprivileged application users and execution boundaries. Application image
  labels bind the released commit, archive commit, tree and build recipe.
- A bounded mount contract. API receives only its application state mounts and a
  read-only authority socket directory. Portal receives no source or host mounts.
  Caddy receives the exact immutable source, read-only maintenance state and its
  existing data/config/log and temporary mounts. Source-shadowing mounts refuse.
- Actual API packaged file hashes and default UID/GID 999 with authority group
  20000; actual Portal UID 1001 and its image-declared primary GID. No assumption
  equates the Portal UID and GID.
- The installed unit's bytes, root ownership/mode, systemd active state and lack
  of drop-ins/stale configuration. The real authority process must have the exact
  command, executable, working directory and Python source environment; root UID,
  group 20000, no-new-privileges and empty effective/bounding capabilities.
- Socket/parent ownership and permissions, and kernel Unix listener ownership by
  the service's main process. Container and authority identities must remain
  stable through verification.

The verifier issues only read-only inspection commands and packaged-file/identity
probes. It does not send authority operations, change services, mutate Docker
resources or relax maintenance. It still verifies the original Sports repair;
excluding Sports controller checks does not exclude the Ingress extension.

A valid offline record is not proof of deployment or acceptance. The undeployed
preview must refuse live validation. The immutable generation, service and new
containers do not exist in production yet. Host generation/service code and
packaged application image revisions are separate source claims; a later native
verifier revision must not relabel already-built application images.

Schema-2 `inherit`, `prepare-restore` and ordinary-update preflight (including
scope `all`) continue to refuse pending the guarded apply/recovery coordinator.
No dispatcher or publication action is added here. Actual rollout, process-death
recovery, fresh exact private/public acceptance and original-owner archival with
publication completion remain required before releasing maintenance or ownership.
