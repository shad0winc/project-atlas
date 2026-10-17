# Strict dump preparation plus native consumption rollback

This isolated rehearsal composes the pinned strict PostgreSQL dump adapter with
the verified native consumption sequence. It enables no live restore or
production deployment. All application data, JWTs and database commits are
synthetic and remain on disposable owned Docker local volumes or private /tmp
copies. Production paths are never mounted as sources or destinations.

## Evidence that the dump was used

The original synthetic PostgreSQL fixture writes marker `snapshot`, captures a
custom-format dump, then changes its running database marker to `after-dump`.
The original stopped cold cluster therefore differs deliberately from its dump.

The new preparation callback runs the existing hash-pinned Dispatcharr prepare
helper as UID/GID 1000. Its original strict adapter copies the stopped source,
restores the dump only into a clone, validates exact public-table membership,
checks internal role/database preservation, restores original configuration
bytes, and cleanly stops the prepared cluster. The source volume is mounted
read-only. Output goes to a new empty, separately labelled disposable volume.
The helper root filesystem is read-only, with no network, published ports or
privilege escalation, and no additional capabilities.

After verifying the helper's exact receipt and zero exit status, the controller
removes that exact stopped helper ID without force or deleting volumes. Only
then does it copy the prepared cluster into a private operator-owned baseline.
It checks that source cluster and dump byte shapes stayed unchanged and removes
the temporary output volume. Both original fixture apps remain detached; the
original Teamarr volume stays unreferenced.

The raw cold cluster and capture document are retained as `COLD_CLUSTER` and
`COLD_CAPTURE.json` in the private baseline. `STRICT_PREPARED.json` binds those
audit inputs, normalized prepared cluster hash and the native helper receipt.
An updated capture document binds the transformed PostgreSQL baseline. JWT and
Teamarr bytes must stay equal to their raw captured hashes. This transformation
occurs before journal exposure. Any interrupted promotion holds the diagnostic;
there is no automatic reconstruction or production mutation.

The prepared baseline must differ from the raw cold cluster. More decisively,
normal app startup must reveal marker `snapshot`, not `after-dump`. The normal
native write phase then commits `native-consumer-committed` and creates a new
PostgreSQL table. After stopped capture, sealed import, quarantine and rollback,
normal apps must again expose `snapshot` and the new table must be absent.
Those checks repeat after another persistence restart. This rules out passing
by merely reusing the original stopped cluster.

## Composition and retained boundaries

The existing native diagnostic gains an explicit in-process extension hook:
checkpoint, preparation callback and PostgreSQL baseline marker must be passed
together. Its original standalone defaults and source checkpoint guard remain
unchanged. The strict entry point pins the modified component, the preparation
callback, the original adapter/helper and every transitively used support file.
It supplies the reviewed current checkpoint and fixed `snapshot` marker.

The existing consumption journal continues to handle the five filesystem
surfaces. Three surfaces contain real normalized native PostgreSQL, JWT and
Teamarr snapshot bytes. Metadata/policy remain explicit small filesystem
fixtures, not full Sports writer acceptance. Teamarr uses the verified stopped
main/WAL/SHM copy-to-snapshot path and fresh empty restore targets. It remains a
cold checkpoint here; this rehearsal adds strict dump preparation specifically
for PostgreSQL. It does not certify cross-application production backup timing.

Applications write their disposable native volumes, not journal directories.
The lifecycle fence removes app objects before capture. Native writes enter the
journal only through the guarded stopped-state import. Partial import holds;
sealed native hashes must match the capture receipt before recovery. Source
volumes are never restoration targets. Root/1000 ownership conversion and JWT
preservation remain mandatory. Teamarr scheduler is off, dry run is true and
cache refresh is skipped. No network or published ports are enabled.

The controller assumes trusted serial operation, not arbitrary concurrent
privileged Docker/filesystem mutation. Existing strict adapter, publication,
consumer process-death and lifecycle retry checks remain separate supporting
evidence. This composition adds no hardware power-loss certification, direct
native journal exposure, full metadata integration, authenticated business API
UAT or live 16-surface orchestration. Production gates remain closed.

## Verification

From the new feature worktree, before committing:

```sh
git diff --check
python -B -m pytest -q tests/core
python -B scripts/diagnostics/sports-strict-consumption-drill.py
```

Overall PASS requires strict preparation, changed native database commits,
quarantine/rollback, normal restored startup, another persistence restart, JWT
preservation, successful owned-resource cleanup and unchanged production
identity/mount observations, deployment pointer and clean canonical checkout.
The diagnostic reports only fixed phase messages and bounded synthetic receipts.
No tool stderr, database contents, JWT bytes, application environment or logs are
printed; only an allowlisted native helper failure category may be forwarded.

Unit tests cover strict receipt typing/flags, raw capture tampering, unchanged
cluster rejection, existing audit preservation, interrupted baseline promotion,
marker program generation and invalid extension combinations. Local UID 1000
assignment and real native/PostgreSQL/Docker execution require CT100, as in the
underlying native consumption candidate.
