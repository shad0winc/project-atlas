# Reviewed acquisition factory configuration

This source change provides default-off production factory wiring. It creates no native profiles, migrates no registry, and enables no recovery callback. Deploying the code with the opt-in absent or `0` preserves the legacy provider, including its existing category server settings. Configuration is not inspected while disabled. The discovery API also uses this provider factory; an enabled but invalid configuration makes discovery unavailable rather than silently using another route.

## Activation contract

`ATLAS_ACQUISITION_ROUTING_ENABLED` accepts only stripped `0` or `1` and defaults to `0`. Both request API and scheduler validate before provider construction: enabled routing requires an already migrated schema-2 repository and `ATLAS_SUBMISSION_RECOVERY_ENABLED=1`. The provider builder itself does not open a registry. Direct callers must enforce their own mutation eligibility; the discovery caller only reads metadata. These checks do not prove other running processes have identical environments. Coherent generation/configuration verification and activation remain a separate reviewed operation.

Enabled routing requires a private, absolute `ATLAS_ACQUISITION_ROUTING_CONFIG` path and an exact lowercase SHA256 in `ATLAS_ACQUISITION_ROUTING_SHA256`. The file is read-only during construction. It must be a regular, singly linked file owned by root or the effective process user, mode `0600` or `0640`, at most 64 KiB. Symlink files/parents, FIFOs, relative paths, `..` components, duplicate JSON fields, nonfinite JSON values, changed files, and digest mismatches fail closed. Check accessible paths, owners/groups and mounts for both the API container and scheduler before activation; this patch installs no configuration or credentials.

The hash binds configuration bytes to an operator-reviewed mapping, not to proof of native profile contents. Credentials referenced from the environment are not covered by that digest. Never dump the file, provider repr, full environment or credentials as a troubleshooting step.

## Configuration shape

The document has exactly `schema_version: 1` and `categories`. This configuration version is independent of request registry schema 2. Categories are exactly `movie`, `tv`, `anime_movie`, `anime_tv`. Each has exactly:

| Field | Contract |
| --- | --- |
| `server_id` | Nonnegative integer; must match the corresponding existing `ATLAS_JELLYSEERR_*_SERVER_ID` |
| `arr_url` | Explicit trusted HTTP(S) Arr endpoint ending in `/api/v3`; may include a safe URL-base prefix |
| `api_key_env` | Uppercase environment variable name referencing a backend-only credential |
| `profiles` | Exact audio modes `english_preferred`, `english_required`, `original_subbed`, each with a positive integer native profile ID |

Each category must have three distinct profile IDs. IDs may repeat in different native instances. Four canonical URL bindings must be distinct; movie/anime_movie and tv/anime_tv Seerr IDs must differ within their respective server collections. This rejects identical URL aliases differing only in hostname case, explicit default port or trailing slash; it cannot detect different DNS names pointing to the same backend. Native exact-instance verification remains required.

Seerr URL/key continue to use `ATLAS_JELLYSEERR_URL` (with the existing fallback when absent) and `ATLAS_JELLYSEERR_API_KEY`. Native credentials come only from the explicitly referenced backend environment variables. URL user-info, query strings, fragments, whitespace, backslashes, dot traversal and invalid ports are rejected. The configuration cannot add arbitrary transport parameters or credential values.

No ready-to-activate JSON with guessed IDs ships. The observed production profiles are ID 7 in each instance; this does not supply three policies and must not be substituted for twelve verified mapping entries. Disposable-environment IDs are not production IDs.

## Transport and ownership

Construction copies immutable bindings/maps and makes no network call. The TV identity resolver lazily uses a GET-only metadata transport restricted to `/api/v1/tv/<canonical-positive-TMDB-ID>`. It disables redirects, uses a ten-second timeout and a 2 MB response cap, and rejects duplicate/nonfinite JSON fields. Seerr identity resolution then corroborates the exact TMDB and TVDB identities. Existing bound Arr managed-profile inventory validation and mismatching shared-title profile barriers remain unchanged. No title matching, mutation transport or POST replay is introduced.

## Evidence boundaries

Tests establish lazy configuration/guard behavior, unsafe/partial mapping rejection, bounded metadata handling and matching API/scheduler construction. They do not establish native ranking or language matching. The fresh production inventory shows all active profiles exclude 2160p acquisition and all four instances use `preferAndUpgrade`. Native policy review must account for PROPER/REPACK revision precedence; changing that setting affects an entire native instance and is not isolated by allocating profiles.

Before activation, obtain reviewed native profile contents/IDs, all three language policies, desired resolution ordering, trusted credential/endpoint bindings, exact existing-title conflict behavior, coherent API/scheduler configuration, explicit schema migration/recovery enablement and native uncertain/delayed submission evidence. Preserve receipt-free barriers and all-season rejection. Imported spoken audio and full English dialogue subtitles remain separate evidence. Preserve exact episode/future-follow/full-readiness, retention, Sports shared-upstream/capacity/stop-isolation, hardware/device, operations and separately agreed reset gates. Nothing here closes them.
