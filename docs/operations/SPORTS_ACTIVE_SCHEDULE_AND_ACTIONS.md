# Active schedule freshness and curated actions

The October 31 acceptance receipt showed Cavaliers at Bucks at
2026-11-01T00:00:00Z (8 PM Eastern on October 31). Exact ESPN home/away team IDs
matched the Cavaliers directory entry. The upcoming window started at 00:12Z,
so that already-started fixture correctly fell outside that specific window.
The older TheSportsDB result is a separate provider result, not evidence of an
ESPN team-filter error or permission to alias provider identities.

The UTC date rollover incorrectly let an active October 31 scoreboard keep a
one-hour past-date cache lifetime. Existing future buckets also retained their
long future lifetime when promoted to the current date. The broker and the
cache-only curated reader now shorten effective expiry to observed time plus
the configured current TTL for the current UTC day, provider-reported live
events, and scheduled starts from six hours ago through one hour ahead. This
never extends expiry, renews an observation, infers live status from time, or
changes a provider/event/team identity. Short lifetimes are persisted on new
fetches; existing snapshots are aged conservatively on read without mutation.

The worker prioritizes due active scoreboards with the current date. One fetch
per tick, existing shared locks, hourly attempt limits, unknown-outcome holds,
and provider cooldowns remain authoritative. Active cross-date buckets can
increase demand beyond the original baseline nominal-cadence estimate. The
existing hard hourly budget still limits all attempts; freshness is not an SLA
and a budget hold must remain visible. No budget or configuration is increased.

The Portal reads the selected shared schedule at most once per minute while
visible, honoring longer retry delays and canceling superseded reads. These
GETs never fetch providers. The selected curated snapshot also participates in
the existing followed live projection, with source-scoped de-duplication and
newer terminal revisions taking precedence. Existing TheSportsDB follows are
not migrated to ESPN, so follow the competition or participant in the curated
browser to save its ESPN identity. The rolling upcoming window is labeled as
excluding already-started games; Today remains the local calendar-day view.
Times include the device timezone and each event's own observation age.

Cards expose participant and event follows. Event follows retain the existing
private API subscription path. A fresh provider-reported live card can check
existing Atlas availability and open only the exact channel returned by that
service. Missing availability is explained without guessing a title match or
inventing stream coverage. ESPN metadata is not registered as a playback or
recording provider. Recording stays unavailable, and no existing streams,
guide bindings, provider accounts, subscriptions, or recording intents are
rewritten. A broader independently reviewed event-to-playback mapping remains
necessary where ESPN event identities have no configured channel binding.

This source PR does not activate a runtime, warm a cache, reopen maintenance,
send an invitation, or prove playback acceptance. A new writer/Portal build,
HTTP/browser review and deployment lineage are required after acceptance.
