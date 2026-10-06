# Acquisition environment wiring

The API Compose service passes the acquisition routing switch, the private routing
configuration path and SHA-256, and four native API credential references from the
operator environment. Routing and submission recovery default to `0`; every other added value defaults
to an empty string. Ordinary deployments remain valid without these settings.

Keep private configuration and credential values outside version control. Native
API keys must never appear in Compose output, review packets, or logs. Do not
change Jellyseerr default profiles or existing native title assignments to stage
this configuration.

The Atlas CLI already loads `.env` with automatic export before invoking scheduler
children. This change does not alter that behavior. The API service also receives the
explicit submission recovery switch, which defaults to `0`. Keep the API and
scheduler settings consistent during a guarded activation transaction.

This patch only supplies environment wiring. Deploying it does not install a
routing configuration, migrate request records, enable routing or recovery, or
prove an acquisition pipeline. Those actions require their own guarded steps.
Before activation, reconcile legacy request audio policies, verify profile drift,
review the global PROPER/REPACK policy, and validate the actual acquisition and
import path. Synthetic ranking fixtures do not establish spoken audio or full
subtitle availability.
