# Sports recovery preparation association

`scripts/lib/sports-recovery-association.py` binds a validated unified Sports
bundle to a separately validated, cleanly stopped PostgreSQL preparation.
It is a callable source primitive, with no live restore command or destination.

Call `associate(bundle_root, postgres_root, database=..., admin_role=...)` only
with isolated private prepared workspaces owned by the calling UID. Prepare the
bundle and cluster under that identity beforehand. The association does not
change ownership, acquire cold copies, run pg_restore or start PostgreSQL.
Native revalidation uses the existing read-only pg_controldata checks.

Both validators must pass. Native artifacts must be captured, not absent. The
PostgreSQL receipt's source dump hash must equal the bundle's Dispatcharr dump
hash, and the reviewed database/admin identifiers must match. The association
binds the complete BUNDLE.json and PREPARED.json bytes, including the bundle's
JWT, Teamarr, metadata, policy and ownership plan references and the PostgreSQL
source/prepared cluster hashes. All referenced content is revalidated.

Success writes only a new private `/tmp/project-atlas-sports-association.*`
workspace containing a fsynced ASSOCIATION.json. Input observations are repeated
before publication and validated afterward. Failure removes only this newly
created workspace. Input artifacts and their manifests are not edited.

`validate_association(workspace)` revalidates both complete input workspaces and
their bound documents. Any changed content, cluster state, identifiers, document,
missing input or receipt flag invalidates the association. Preserve all three
workspaces; the receipt does not copy or own the associated state.

The result remains `associated-not-live-ready` with
`ready_for_live_apply:false`. This is an association of reviewed bytes, not proof
that independently captured surfaces share one application-consistent generation,
nor certification of intended numeric production identities. A private operator
can rewrite artifacts and receipts; these are integrity guards, not signatures.

Core tests exercise real bundle preparation and file validation, while replacing
only PostgreSQL native commands for portability. The previous isolated native
preparation rehearsal supplies the separate PostgreSQL execution evidence.

Production cold-copy acquisition, shutdown, ownership attestation, durable
publication/rollback across services, crash recovery, remount/restart acceptance
and production Sports UAT remain open. Existing format-2/3 live restore blocks
and the 16-surface replacement engine remain unchanged.
