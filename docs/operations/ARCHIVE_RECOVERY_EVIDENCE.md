# Fresh evidence after an archive interruption

`ArchiveRecoveryEvidence` is a host-only evidence component, not a production
archival driver or release permit. It has no CLI. It requires a separately
source-verified `PrivateArchiveEvidence` instance and its verified native owner
probe and inherited exclusive scheduler flock.

The original private receipt may have expired after an interruption. It remains
expired and byte-identical. The original preservation plan and archive intent
also remain unchanged. Recovery creates one additional eight-file attempt under
`private-attempts` with a distinct scope, `fresh-held-archive-recovery-evidence`.
It must never be presented as a fresh original private acceptance receipt.

Only a journaled native archive phase is eligible: durable intent with a live
owner, moved owner awaiting parent synchronization, or completed archival.
Owner-live without an archive intent refuses. The new attempt binds the exact
existing archive-intent hash, preservation-plan hash, original preserved private
context, current phase, historical collector source, recovery/policy source
hashes, provider availability, boot and wall/monotonic start times.

The trusted host driver must execute the committed historical runtime, doctor
and verify gates into the new attempt's exclusive log/exit files, preserving all
previous attempts. `finish` validates zero exits and native success semantics,
context and phase stability, provider usability, exact inventory, provenance and
at-most-300-second freshness before making logs durable and publishing the new
receipt. `validate` repeats these checks without refreshing or rewriting it.
Changed context, phase, source, boot, logs or intent refuses. Expired recovery
evidence refuses; a new independently bound recovery attempt is required.

This does not authorize an archive retry on its own. Before the original move,
the immutable host-driver admission must explicitly declare this recovery
method, its trusted source/provenance and recovery-evidence selection rules.
The retry keeps that admission object and native archive intent byte-identical.
It cannot substitute a different admission dictionary or retrofit recovery
authorization into an already sealed intent. A verified host policy may consume
fresh recovery evidence under that predeclared method, together with current
CI, external admission/freshness, complete phase-aware native inspection and
scheduler checks. None of those additional proofs are granted by this receipt.

There is no fallback for changed runtime context, ambiguous owner location,
corrupt intent, or an undeclared recovery policy. Those require operator review.
The code never moves an owner, completes publication, disables maintenance,
reverses a rename, edits old receipts, or changes the preserved plan/intent.

Tests use real native publication/owner fixtures, Git source, flocks and Linux
owner renames. Gate output and Docker/provider responses are explicit fixtures;
fixture admission callbacks do not represent production authority.
