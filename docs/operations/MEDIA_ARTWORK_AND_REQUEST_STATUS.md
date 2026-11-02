# Media artwork and request status

Discovery cards render the selected title's provider poster filename through the
TMDB image CDN. Only a single image filename with an allowed raster extension
is accepted. Title, year, request identity, and season selection remain visible.
Missing or failed artwork gets a clear placeholder; no unrelated image is used.

Library cards request the exact Jellyfin item ID through Atlas's existing
`media.read` authorization boundary. The API reads a bounded primary image from
the configured Jellyfin server and returns raster bytes as base64 JSON, keeping
provider credentials server-side. The browser uses the existing authenticated
client, aborts reads on unmount, and never reuses an image across item identities.
Provider redirects, active image formats, oversized responses, and arbitrary
image URLs are refused. Responses are private and not cached.

The deployed provider review observed a completed request whose media status is
7 (deleted), while Atlas still recorded processing. Request normalization now
maps deleted media to failed, as it already does for blocklisted media. It does
not recreate requests or download deleted content. Partial seasons retain their
existing importing state; Ready to Watch still requires Jellyfin readiness.

A reconciliation pass containing failed requests now exits nonzero after
printing the existing JSON summary, including when submission recovery is on.
This lets scheduler health reflect request failures rather than only successful
execution of the callback. The recovery and acquisition feature flags are
unchanged.

## Validation and rollout

Source validation covers provider-state normalization, failed reconciliation
exit status, authenticated artwork access, exact item identity, redirect and
credential containment, byte and format bounds, unavailable artwork, browser
fallback, item changes, and request cancellation on unmount. Existing Portal
Media, catalog/discovery API, and request regression suites are also run.

This source change does not deploy runtime images, modify request registries,
start playback, or complete Media acceptance. Promote through the RC and main
release gates, then prepare image-bound deployment records for API, Portal, and
the scheduler source. Existing maintenance and rollback records must be retained.

After deployment, inspect Discovery and Library with exact title/year artwork,
missing artwork, narrow screens, and expired authentication. Observe a natural
scheduler pass to confirm deleted media leaves processing and per-request
failures appear in scheduler health. A fresh user-selected request and actual
Media playback remain separate acceptance checks. Native language, dub,
subtitle, and acquisition-policy provenance remain in the broader Media
acceptance checklist.

TMDB image URL reference: https://developer.themoviedb.org/docs/image-basics
