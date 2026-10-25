# Held publication fence completion

This host-only mechanism archives the exact publication marker after the original
owner has been archived. It does not change the current pointer, deployment
records, rollout journals, original owner archive, service configuration, or
maintenance enabled file. There is no CLI or automatic production activation.

The original marker is renamed with Linux RENAME_NOREPLACE into
`maintenance/publication-completions/<publication>/publication-pending`. Its inode,
owner, mode, link count and bytes remain bound to the supplied plan. A durable
intent precedes the move; both rename parents are fsynced before completion.

The inherited scheduler exclusion must already be exclusively held. The child
closes duplicates without unlocking the parent's open description. An explicit,
trusted `admit(plan, admission, state)` callback is mandatory at three boundaries;
it must return None or refuse. A production driver must prove native runtime,
archived owner identity, source/CI, and applicable fresh acceptance independently.
The plan and structural completion records confer no acceptance authority.

`inspect()` recognizes before-intent, intent-durable-marker-live,
marker-archived-needs-completion, and completed-maintenance-handoff-pending.
Existing intents cannot be adopted with different admission. Symlinks, duplicate
marker locations, changed bytes or identity, unexpected files, unrelated control
transitions and nonexclusive descriptors are rejected. Partial writes are retained
for host review; they are not overwritten or silently repaired.

A completion-owned `control-pending` fence is retained, including on success.
Ordinary maintenance disable remains blocked. Generic `recover_hold` refuses this
owned fence. Removing it is a separate host handoff requiring phase-aware native
inspection and an explicit durable handoff protocol. This source change alone is
not a production completion driver and must never be used to reopen Atlas.

Production integration still requires a promoted, pinned driver and inspection
adapter that validates the owned control fence and archived marker at their new
locations without waiving native runtime or archive checks. Both source and API
maintenance authority compatibility must be established before production use.
Do not invoke the older marker-required inspector after a marker move and treat
its refusal as permission to bypass checks.

The focused tests use real filesystem identities, Linux no-replace rename and
inherited flock, with explicit fixture-only admission. They test interruption and
retry at each checkpoint, admission refusal, ownership fence preservation,
conflicting operations and generic hold-repair refusal. They do not establish
production admission, service health, browser access, or playback acceptance.
