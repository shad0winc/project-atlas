# Held component rollout journal engine

This stage supplies a journal engine and a private file-backed action adapter.
A production Docker/systemd/source adapter is not implemented or admitted here.
There is no public CLI or ordinary-update entry point. The existing schema-2
update, inheritance and restore refusals remain in force.

The engine requires the exact original recovery owner and its inherited exclusive
scheduler flock. It retains the owner directory/file identities and bytes, the
current pointer and maintenance flag. It refuses pending maintenance transitions
or publication. Plans pin protected baseline/failed-record evidence and four
artifact inputs: application archive, target recipe, rollback recipe and authority
unit. Each surface has a normalized before/after fingerprint and an exact before
runtime identity. Observations contain both normalized state and runtime identity.
A future production adapter must derive and verify these values from the pinned
recipes, source, immutable image IDs and installed authority boundary; caller
assertions and a mock adapter are not production evidence.

Forward surface order is source generation, authority unit, authority service,
API, Portal, then Caddy. Each action receives durable intent before execution and
a durable observation afterward. Rollback reverses completed surfaces, starting
with Caddy when it was applied, and stops/undoes the authority only after the
applications are restored. Source generations and repair evidence must be retained
by the eventual production adapter even after rollback; rollback means removal
from active use, not deletion of recovery evidence.

An explicit resume inspects an interrupted action. The exact old observation can
be retried; a verified target fingerprint can be recorded as an observed result
without repeating the action. An unknown result refuses both forward retry and
blind rollback. Every already-completed surface must retain its recorded runtime
identity; a same-image replacement or process restart after a receipt is drift.
The eventual adapter must bind target observations to this rollout's ownership
labels and independently verify all target properties before returning them.

Events are append-only, sequenced and linked by hashes. An explicit resume
reflushes complete visible evidence before trusting it after any fsync uncertainty.
Partial, foreign, reordered or conflicting journals are retained and refused.
Journal preparation is idempotent only for an exact complete plan/context. A
partial preparation never advances to actions automatically.

Final adapter verification must return True. The resulting journal state means
only that the component boundary was observed while held. It is not private/public
acceptance, a new deployment record, a pointer publication, an owner archival or a
permission to reopen. A rollback likewise records an observed held boundary; it
does not claim an operational backup restore.

Tests use real private filesystem state, inherited flock and SIGKILL at every
forward and reverse intent/action/completion boundary. They verify evidence and
owner retention, exact resume, reverse order, drift refusal, artifact changes,
partial journals and fsync uncertainty. These process-death tests do not prove
physical power-loss durability.
