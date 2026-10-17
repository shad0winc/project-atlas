# Synthetic combined Sports publication and consumer-copy restart rehearsal

This diagnostic combines the existing bundle, native PostgreSQL preparation,
association and five-surface publication helpers with pinned-image Dispatcharr
and Teamarr fixtures. It never accepts production destinations, credentials,
feeds, bind mounts or a live-restore flag. Production restore gates are unchanged.

## Exact acceptance boundary

The publication journal requires exact current/old/incoming hashes for recovery.
Normal application startup and later writes can change database files. Therefore
applications in this diagnostic open **disposable copies** of the published
state, never the journal's current or preserved old trees. This tests combined
publication, consumer-copy startup/persistence/ownership and independent journal
undo. It does not certify rollback of application-mutated publication trees or
the production live transaction. That remains a separate design and acceptance
gate; do not use this PASS as permission to enable format-3 live restore.

The five journal surfaces are PostgreSQL, Dispatcharr JWT, Teamarr SQLite,
Sports metadata database/lock, and metadata refresh policy.

## Lifecycle

1. Require clean canonical source at main
   `d5f3a813868fde036f517e47c412b08490266a52`, unchanged deployment
   `update-20261015T211211Z-632971`, installed pinned images and all source pins.
2. Run the pinned Dispatcharr and Teamarr component diagnostics against their
   disposable fixtures. Reuse their code with an explicitly reviewed combined
   checkpoint and label; their source files and standalone guards are unchanged.
   Normalize Docker mount-list order without dropping any fields. Defer only
   their labelled fixture cleanup until the combined rehearsal finishes. Require
   all retained component containers exited before using their source volumes.
3. A root collection helper reads only the stopped synthetic volume mounts,
   copies original/new JWT identities and the detached Teamarr backup into an
   empty private publication volume, and assigns preparing identity 1000:1000.
   It never opens a production path or prints identity bytes.
4. A nonroot helper prepares a real native PostgreSQL clone from the stopped
   original fixture and dump. It builds a format-3 Sports bundle containing the
   copied JWT, real Teamarr snapshot and synthetic metadata/policy. Its fake alias
   enrollment is fixture data, not evidence for production identity enrollment.
   Metadata budget markers distinguish old (111) and new (123) state; canonical
   synthetic owner IDs distinguish the alias generations. Both policies remain
   disabled, with different serialized bytes. No refresh worker is started.
5. Validate the bundle and native receipt, associate them, stage all five
   surfaces and apply the existing durable publication journal. Preserve old
   state. Remove temporary association/bundle/native inputs, proving undo does
   not require those source workspaces after publication.
6. A separate root helper mounts the journal read-only and exports all five
   surfaces to three empty disposable consumer volumes. Verify source digests,
   source stability and copied contents. Assign numeric identities only in these
   new copies: PostgreSQL 1000:1000/0700/0600, JWT 0:0/0600, Teamarr 0:0/0600,
   metadata 1000:1000/0700/0600, policy 0:1000/0750/0640.
7. Start normal Dispatcharr and Teamarr against their respective copies. Require
   component readiness, snapshot rows and no post-dump PostgreSQL stale table.
   Make fixture-only writes, stop cleanly, restart both applications and verify
   persistence. Teamarr uses SCHEDULER=off, DRY_RUN=true and skipped cache refresh.
8. A 1000:1000 read-only metadata probe checks alias ownership, attempt state,
   private database/lock modes and root-owned policy readability. It tests the
   writer identity's read contract, not startup of the Sports writer service.
   A root verification helper checks JWT bytes/ownership after startup, clean
   PostgreSQL shutdown and a detached validation of Teamarr's stopped WAL set.
9. Recover the untouched journal twice. Require all five preserved old hashes,
   old metadata alias/budget state, reverted status and unchanged original cold
   PostgreSQL/dump hashes. Consumer copies are not production destinations and
   are discarded separately; undo does not relabel them as reverted consumers.
10. Remove combined helper/consumer containers first, freeing their retained
    input-volume references, then clean each component in its original
    container-before-volume order. Clean only exact labelled resources, continuing other
    cleanup attempts after a failure. Recheck production image/PID/start/mount
    observations and deployment pointer even when cleanup fails. No overall
    PASS is emitted on any failure. Attempt journal undo on consumer-check errors
    when the helper completed publication; preserve failure status regardless.

## Operational scope

The normal pinned app images and original entrypoints are reused. All fixture
containers have no network, ports, production environment, privilege escalation
or Docker log output. Resource limits and the component AIO capability bounds
remain. Helpers use read-only roots and bounded tmpfs. Root conversion helpers
receive only CHOWN, DAC_OVERRIDE and FOWNER; nonroot stages have no capabilities.
Mount sets and access modes are inspected before helpers execute.

Component progress is forwarded, but their final receipts are suppressed because
cleanup is intentionally deferred. The final combined PASS is emitted only after
joint resource cleanup and production observation checks. The mount-order fix
is applied to retained component observations as well.

Run this diagnostic in the candidate worktree before committing, following the
full core suite. Local unit tests cannot prove real image startup, mounted-volume
ownership or native PostgreSQL behavior. Real CT100 acceptance is required.
The rehearsal may take several minutes and temporarily retains multiple stopped
synthetic volumes; it cleans them at the end. A reported failure is not a reason
to weaken a guard or enable live restore.

Remaining gates include direct consumer mutation and durable live rollback,
production writer shutdown under load, authenticated functional/playback UAT,
coherent cross-surface capture generation, all 16 filesystem surfaces and the
release/deployment acceptance path. No production activation is performed here.
