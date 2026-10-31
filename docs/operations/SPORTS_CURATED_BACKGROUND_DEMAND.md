# Automatic schedule demand with curated browsing

The original followed-schedule loop includes every provider. Adding a cache-only schedule browser does not by itself stop that loop's automatic TheSportsDB requests.

While the curated catalog is enabled, loading, or unavailable, automatic followed refresh accepts only ESPN identities. Those schedule reads use the existing metadata discovery cache. A catalog that explicitly reports disabled retains the original multi-provider polling behavior. This prevents a page-load race from issuing an external-provider batch before catalog discovery completes.

Existing follows and their provider IDs remain unchanged. An explicit View upcoming action for a search provider performs one cancellable, bounded schedule operation, with no repeating timer. It includes that provider's enabled follows so the existing per-provider snapshot remains coherent; the visible selection still filters to the chosen team or league. Failures retain the last successful snapshot. New browse/search actions and unmount cancel an outstanding manual browse. Normal configured channel and playback/recording controls are preserved.

Older search-provider follows no longer supply an automatically refreshed live projection while curated browsing is active. Follow a competition/team in the curated browser for cache-backed automatic metadata updates. No follows or recording intents are migrated or rewritten automatically.

Validation: fifteen deterministic frontend scenarios, including execution of the actual refresh loop with mixed-provider follows while the catalog is enabled, disabled, loading or unavailable. Full Portal lint, typecheck, tests and build are required before push. Source-only: no API/writer/controller change, refresh activation, provider request, deployment, publication or invitation.
