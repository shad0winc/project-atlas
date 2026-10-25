# Publication completion maintenance handoff

Publication completion archives the publication marker while retaining its owned
`maintenance/control-pending` fence. `PublicationCompletion.handoff` returns that
completed publication to ordinary enabled maintenance. It never disables
maintenance, reopens access, changes deployments, or grants release acceptance.

The host driver must verify promoted source and CI, the original completion
plan/admission, current native runtime, archived owner, and fresh phase-bound
private and external admission. The mandatory callback runs before handoff
intent, before the control-fence rename, and after the rename. A callback returns
`None` only after independently verifying the actual supplied state.

The mechanism seals `handoff-intent.json` beside the completion records. It binds
the unchanged completion intent/completed digests, exact control-fence identity,
exact enabled-flag identity, and host handoff admission. It moves only the owned
control fence to `control-pending` in that completion folder, using same-filesystem
no-replace rename, then synchronizes both parents and records
`handoff-completed.json`. Both original completion records remain unchanged.

Inspection distinguishes durable intent with live fence, archived fence needing
completion, and completed handoff with maintenance held. Every state validates
the original publication marker, current pointer, owner archive records, enabled
flag, and unique owned control-fence location. Resume requires the same sealed
handoff admission plus newly verified callbacks. A completion retry is refused
once handoff starts, so it cannot recreate the archived control fence.

An interruption preserves the actual fence location, enabled maintenance and
all records. The host must inspect the actual phase before any retry; it must
never remove a fence manually or substitute generic hold repair. Host/native
inspection integration and production handoff are separate from this source
change. Public/member acceptance, Sports deployment and Media validation remain
separate work.
