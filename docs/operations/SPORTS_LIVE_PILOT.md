# Live Sports pilot boundary

The first pilot uses managed Atlas live Sports. Provider VOD, provider series,
and catch-up playback remain unavailable; Jellyfin Media is a separate surface.

The image installs a default-off ingress guard using an exact upstream settings
hash. `ATLAS_SPORTS_PILOT_MODE=live-only` requires strict verified live mode and
the persisted ledger-migrated flag. Invalid or partial pilot configuration
refuses admission. The middleware rejects VOD/catch-up proxy, XC movie/series,
timeshift path/query, VOD/catch-up API, and HLS ingress before view dispatch.
Module checks reject aliases to excluded playback view packages.

The live wrapper refuses direct Stream previews and requires a configured
classifier and verified policy. An authoritative unmanaged classification cannot
fall back to legacy during the pilot. Existing network denials and allocation-free
HEAD/OPTIONS behavior remain; the original GET body stays unchanged.

No cutover is authorized by this source change. Before activation, validate the
new image with actual Django routing, audit remaining playback/API aliases, drain
all old upstream sessions, capture a fresh backup, install the dedicated policy
token/scope key, migrate the rehearsed registries, and execute the guarded ledger
cutover. Prove embedded live playback, sharing, capacity and per-user release
before admitting a pilot member. Keep maintenance enabled until acceptance.

This change does not deploy an image, change production environment flags,
migrate registries, restart services, or publish a 1.0 release.
