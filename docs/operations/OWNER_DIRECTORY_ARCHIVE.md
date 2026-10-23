# Owner directory archival mechanism

`atlas.deployment_owner_archive.OwnerArchive` supplies a host-only filesystem
mechanism for a future reviewed release driver. It has no CLI, HTTP or socket
entry point. Adding this module does not invoke it, release production ownership,
complete a publication or reopen maintenance.

The existing preservation plan is a pinned identity record. Its private receipt
is not renewed, and the plan grants no release permission. A production driver
must independently bind its promoted executing source and CI, fresh private
acceptance of the preserved runtime context, and separately collected external
maintenance admission evidence. A browser summary or caller-supplied success
boolean cannot replace those checks.

`archive(publication, plan_sha256, admission, admit=verifier)` requires an explicit
host verifier. It receives a canonical copy of the admission evidence and the
current phase twice before any move. It must raise on refusal. The evidence is
sealed unchanged in the archive intent. Retries require that same evidence and
the verifier again; visibility of completion does not skip validation. The module
does not implement that release policy or establish the truth of remote evidence.
There is deliberately no permissive default verifier.

The driver must distinguish the source of its new archive code from the source
of the existing collector and scheduler generation. It must not relabel the
historical runtime, rewrite a generation environment link or import temporary
substitutes to make those sources appear identical. Existing owner-live collectors
also reject new archive journal entries and cannot be blindly replayed after a
move. That phase-aware integration and its durable standalone inspector must be
developed and promoted before production archival.

Under the exact inherited exclusive scheduler flock, the mechanism checks:

- the pinned preservation plan, original owner inventory and owner copy;
- the exact published current pointer, original intent and held boundary;
- maintenance enabled, no competing control transition and the exact publication
  fence;
- exactly one live or archived owner location, retaining directory and file
  device/inode, bytes, modes, ownership and link count.

It seals and flushes an archive intent before moving. Linux `renameat2` with
`RENAME_NOREPLACE` moves the whole directory on the same filesystem. There is no
overwrite, copy/delete fallback, cleanup or implicit reversal. It flushes the
archive directory and both parents, then seals a completion record. An explicit
retry flushes visible intent and completion bytes again, including after a prior
fsync error.

Read-only `inspect` classifies these phases without refreshing admission:

| Phase | Meaning |
| --- | --- |
| `owner-live` | Original directory retained; no archive intent |
| `intent-durable-owner-live` | Complete visible intent; original owner retained |
| `moved-needs-parent-sync` | Original directory moved; completion not established |
| `archived` | Exact completion record visible and identity verified |

Inspection reports visible state, not proof of physical power-loss durability.
Missing/both locations, foreign destinations, unexpected journal entries,
unexplained moves or partial/conflicting evidence refuse and remain preserved.
Inspection of a visible intent cannot prove that a previous fsync succeeded;
only an explicit admitted retry performs the required flushes.

Every successful archive leaves maintenance enabled and `publication-pending`
unchanged. Public reopening remains forbidden. Moving `update.lock` makes the
ordinary scheduler's recovery-lock check clear, so the future driver must assess
that consequence explicitly while holding exclusion and verify freshness after
handoff. This module neither starts nor stops a scheduler or container. Publication
marker completion and controlled public acceptance require a separate protocol.

Tests use real native publication and owner-plan fixtures, actual inherited flock
and no-replace directory rename. Admission and Docker data are explicit test
fixtures. Refusal, conflicting evidence, fsync errors, destination races and
SIGKILL at four archival checkpoints are covered. These tests do not establish
production release authority, physical power-loss recovery or backup restoration.
