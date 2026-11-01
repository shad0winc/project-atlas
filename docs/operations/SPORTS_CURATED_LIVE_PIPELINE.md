# Followed ESPN cache events in the live pipeline

Curated schedule browsing uses ESPN identities, while the existing controller
provisions and publishes events from the legacy games-state discovery path.
Creating a channel alone does not bridge that gap: a later feed generation can
omit the ESPN event. Team labels do not make an old TheSportsDB event equivalent.

This change adds an opt-in projection from the authenticated writer's existing
curated cache endpoints. Fresh scheduled/live events within the pregame/active
window must match an exact ESPN team, league, or event follow. Team names come
from the matching ESPN directory. Final, unknown, cancelled, stale, and unmatched
events are excluded. Start times never establish a live status.

One cycle supplies the same projected events to existing content resolution,
channel reconciliation, and feed rendering. Existing LiveSource authorization
remains required for an event to enter M3U/XMLTV. Feed publication and exact
numeric Jellyfin binding convergence continue through the existing pipeline.
ESPN events are not added to recording planning or persisted as legacy games.
The original provider/event identities and channels remain separate. Imported
stream reuse across events does not authorize overwriting their bindings.

The feature defaults off. A separately reviewed controller deployment must set
`ATLAS_SPORTS_CURATED_LIVE_ENABLED=1`, provide the internal
`ATLAS_SPORTS_WRITER_URL` and `ATLAS_SPORTS_WRITER_TOKEN`, and bind the new source
and images to publication/recovery records. No controller runtime is altered by
the source PR helper. The controller needs permission to read the curated writer
endpoints; credential scope must be checked during deployment preparation.

The reader makes at most ten internal GETs per cycle, with a twenty-second
deadline, three-second request timeout, four-MiB response limit and no redirects
or environment proxy. It never calls a public sports provider or refreshes a
playlist. Disabled mode and no ESPN follows issue no requests. Malformed/cache
transport failures are explicit errors rather than authoritative empty schedules.
Imported stream metadata is reused once per backend account in a cycle.

This does not prove a team's imported stream is actually airing the scheduled
game. Private content, playback, shared-viewer, session cleanup, controller-cycle
continuity, feed/Jellyfin convergence and rollback acceptance remain required
before a public reopen. Existing channel creation uncertainty handling is not
expanded by this change; a lost creation response requires reconciliation rather
than an unreviewed operator retry. College sports and ESPN recording remain
unsupported by this integration.
