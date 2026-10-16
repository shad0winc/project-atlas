# Cache-only independent Sports discovery

## Scope and activation

The authenticated private writer can resolve an explicit `provider=espn` through
`MetadataDiscoveryProvider`. The existing search/events, search/teams,
search/leagues, filtered events and follow creation routes are reused. Existing
public Sports API routes and the Portal client already accept an explicit
provider. Portal default search still uses SportsDB; automatic aggregation and
partial-provider result presentation are NOT implemented by this change.

The factory first requires an explicitly enabled refresh policy, then uses only
that policy's supported routes and shared metadata store. The packaged policy
remains disabled, so this change does not activate traffic or production state.
The worker/playback provider registry remains unchanged. No new HTTP route,
external request from discovery, private-state mount for the API, or credential
is introduced.

Supported routes remain the six fixture-backed routes: NFL, NBA, MLB, NHL,
English Premier League and UFC. This is not all-soccer coverage and does not add
wrestling, boxing or smaller fight promotions. UFC is one card per parent event;
bouts/fighters are never projected into home/away teams.

## Identity and completeness

ESPN event/team public IDs use the directory codec, for example
`football-nfl-401873007`; league IDs are exact route strings (`football/nfl`).
The provider remains `espn` through filtering, lookup and saved follows. No
SportsDB IDs are guessed or substituted, and no immutable aliases are enrolled.
Existing SportsDB follows do not automatically acquire an ESPN mapping.

Schedule discovery reads one coherent cache view of yesterday through day seven
for each selected route. Two bounded windows reconcile that same view before
filtering, covering current/recent occurrences and a rolling seven-day future.
Event/team/league filters select a union of exact source identities. Equal-latest
conflicts and unknown event times fail closed. Rows are bounded at 500; excess
results fail rather than truncate silently. Search terms are limited to 128
characters and each filter to 64 IDs. Empty queries read no cache.

All required buckets/directories must be fresh. Missing, invalid or expired
snapshots remain unavailable, not successful empty schedules. A fresh fully
observed empty schedule is a valid empty result. This intentionally withholds
results while any required route cache is incomplete; richer per-provider/route
partial coverage is a subsequent aggregation concern. This is cache coverage,
not proof that the upstream schedule contains every sporting event.

## Live age and recording

Event projection carries original `metadata_observed_at` and
`metadata_expires_at`. The API and Portal validate paired aware timestamps with
positive lifetime at most one hour. Currently Live requires unexpired ESPN
observations and a provider-reported live state, never elapsed start time alone.
Follow refresh revalidates at the earliest observation expiry when sooner than
its normal interval, clearing its live projection before waiting for the request.
Legacy SportsDB rows without metadata age retain their existing behavior.

ESPN follow creation defaults to record=false. Enabling recording on such a
follow is rejected through the existing unsupported-target contract; disabling
it remains allowed. No metadata result creates an Atlas channel, playback URL,
Jellyfin binding, Dispatcharr connection or capacity entitlement.

## Remaining release work

Automatic Portal discovery aggregation, provider/route coverage presentation,
reviewed existing-follow identity mappings, effective capability health,
enabled-policy persistence and recovery/rollback acceptance remain open.
Production metadata activation and Sports UAT have not been performed.
