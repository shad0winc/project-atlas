# Private evidence across owner archival

`PrivateArchiveEvidence` validates an existing native private acceptance receipt
in all four `OwnerArchive.inspect()` phases. It is a read-only component for a
separately reviewed host driver. It has no CLI and cannot capture a receipt,
archive ownership, complete a publication marker, or disable maintenance.

The private collector remains bound to its actual source checkout. In a mixed
runtime recovery this can be the historical collector and environment matching
the published source generation. Do not relabel its source commit or rebind the
generation environment to the newer archival implementation.

The host bootstrap must verify both source packages before import. To keep core
imports isolated, the historical-source child may load this separately pinned
module by file path; it uses the historical Atlas journal/control primitives.
The owner probe must invoke the independently verified native owner inspector
using the same runtime root, original owner, publication, preservation-plan pin
and inherited scheduler flock. Boolean probes and incomplete proofs refuse.
This interface does not make caller-selected code or probe output trustworthy.

Validation proves the inherited exclusive flock without unlocking its parent's
open file description. It rechecks the exact private receipt, before snapshot,
eight-file attempt inventory, native gate log hashes and success semantics,
boot identity, wall and monotonic ages (at most 300 seconds), current provider
health, preservation-plan context, protected publication artifacts, record,
historical clean source, generation and container identity/configuration. It
checks context twice and observes the owner phase before and after. The method
does not refresh timestamps or rewrite any evidence.

This avoids replaying owner-live `_snapshot()`, `state()` or `validate()` after
an archive intent appears or the owner directory moves. Those older contracts
correctly reject a changed journal or missing live owner. The native owner
inspector classifies and verifies the live/archive location instead.

An accepted private result remains evidence only. A production archival driver
must separately verify its own promoted source, exact current protected-branch
CI, external HTTPS admission and freshness, and the complete phase-aware native
rollout/runtime inspection. The original preservation plan is identity evidence,
not a release permit. Capture and consumption belong in one guarded handoff.

Native archival calls admission twice. The phase argument describes its initial
inspection and can still say `owner-live` after the intent becomes durable.
The owner probe must inspect the current phase each time, rather than trusting
that initial argument. Interruption retries must retain the original sealed
archive admission and revalidate it; completion visibility supplies no waiver.

An expired receipt refuses in every phase, including moved or completed phases.
This component cannot recover freshness after a move and has no fallback to
rewrite old receipts, create an owner-live receipt, reverse the rename, or
reopen public access. Such a failure requires a separately reviewed recovery
path while maintenance and the publication fence remain closed. A production
driver must also account for the scheduler being able to resume when the live
owner directory has moved and the parent's flock is released.

Tests use real native journals, clean Git source, inherited flocks, no-replace
directory moves, and SIGKILL interruption boundaries. Docker/provider responses
are explicit fixtures. Test admission is never production CI/external authority.
