# Opt-in HLS diagnostics

Use local browser Console diagnostics to investigate a live player whose buffer stops advancing while the upstream feed and Jellyfin playlist remain active. They are disabled by default and emit no server telemetry.

Enable with `localStorage.setItem("atlas.playback.diagnostics", "1")` in the Atlas site's Console. The setting is checked for each HLS event, including an already open player. Copy `ATLAS_HLS` lines as text. Disable with `localStorage.removeItem("atlas.playback.diagnostics")`.

Each player instance emits at most 200 records. Fragment loading and buffering events are sampled at most once per ten seconds per event type. Errors include nonfatal errors and are not sampled until the cap is reached. Only allowlisted enum-style labels, numeric status/fragment fields, video state and up to eight buffered ranges are emitted. URLs, headers, capabilities, cookies, session identifiers and free-form error text are excluded. Diagnostics failures must not interfere with playback.

This change adds observations only. It does not automatically reopen a stream, seek the live edge, renew authentication or change ownership and cleanup rules. A full raw Console export or HAR can contain unrelated credentials; share only the sanitized `ATLAS_HLS` records. Native-HLS-only browsers do not use these managed-HLS hooks.
