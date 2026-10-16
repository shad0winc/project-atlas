# Dormant Sports metadata runtime packaging

This packages private writer state without enabling metadata traffic. It does
not register ESPN, federate discovery, enroll identities, change doctor/provider
health, or authorize any playback source.

## Deployment contract

The private writer image retains `metadata-refresh.disabled.json` as a disabled
fallback artifact. Canonical Compose reads `/srv/sports-metadata-policy/refresh.json`
from a separate server-owned, read-only directory bind. Provisioning creates only
`{"version":1,"enabled":false}` when this directory is absent; subsequent updates
validate and preserve the exact existing policy bytes. No enabled policy is
installed by this integration. See `SPORTS_METADATA_POLICY.md` for ownership,
recovery and activation limits.

The writer alone mounts
`${ATLAS_RUNTIME_CONFIG_DIR:-/mnt/storage/configs/atlas}/private/sports-metadata`
at `/srv/sports-metadata` read/write. Long bind syntax sets
`create_host_path: false`; Docker cannot silently create a root-owned directory.
The policy bind is also writer-only, read-only and uses `create_host_path: false`.
API, controller, Portal, Caddy and media services receive no new mount.
`stop_grace_period: 35s` exceeds the worker's 25-second join deadline.

After successful pre-update doctor and artifact preparation, canonical
`atlas update ingress|all` provisions the state before maintenance and backup.
Core-only updates do not provision it. The helper resolves the writer's numeric
PUID/PGID from Compose build arguments without printing Compose output or sourcing
operator environment files. The existing runtime configuration root must exist;
it never creates a missing storage root.

A new root-owned private parent is 0700; a new metadata child is writer-owned
0700. Bootstrap creates NEW schema-1 state in a unique private staging directory
on the same filesystem, validates it, then assigns only the newly created
files/directory to the image writer UID/GID and atomically publishes it. SQLite
cannot initialize as the writer through a root-private host parent; the container
will instead access the directory through its direct bind mount. Both database
and lock are 0600. No transport or broker factory is constructed. Existing directories, ownership and modes are
validated without chmod/chown repair. Existing complete state is validated under
the metadata lock, preserving cache, budget and immutable aliases. Partial state,
links, unknown files, unsafe modes and unsupported schemas fail closed. Failed
initial provisioning is retained for review; do not blindly retry or delete it.

## Recovery consequences and remaining gate

Provisioning creates an empty schema-1 database even while refresh is disabled.
Therefore the pre-update backup captures metadata using recovery format 3.
The previously implemented format-3 validator and detached SQLite snapshot apply.
Live native-backend/metadata restore is still unsupported. This packaging is not
permission to deploy before release-specific recovery and rollback evidence is
accepted. A rollback must preserve the metadata directory and immutable identity
records; do not remove state merely because an older image ignores it.

This revision does not bypass the existing degraded SportsDB doctor gate.
The canonical pre-update doctor runs before this bootstrap, so a failed doctor
creates no new metadata directory. Production activation, live policy/database restore and rollback acceptance,
capability health, existing-follow identity mapping and Sports UAT
remain open.

## Validation

`test_sports_metadata_runtime.py` exercises isolated provisioning, schema and
alias preservation, permissions, links, unknown/partial state, Compose identity,
update ordering and the disabled default. The non-root writer read/write test uses an accessible isolated mount-shaped
path and must also run on CT100; restricted user namespaces can only skip that
case locally. Update-transaction fixtures include the metadata bootstrap and
exercise its failure boundary and pre-maintenance ordering.
Use the full Core suite on the isolated feature worktree. Build and render the
writer image through canonical deployment preparation only after release gates
permit deployment. No production bootstrap is part of candidate verification.
