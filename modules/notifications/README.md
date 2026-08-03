# Atlas Notifications

Atlas Notifications is the Runtime Bus consumer responsible for formatting and
delivering Atlas operational and lifecycle notifications.

## Status

The module currently supports:

- Atlas health notifications;
- storage threshold notifications;
- movie notifications;
- television notifications;
- anime movie notifications;
- anime television notifications;
- Sports notifications;
- normalized Media Request lifecycle notifications.

The module can deliver notifications through configured Discord webhooks and
the generic webhook adapter.

## Module ID

```text
notifications
```

## Architectural boundary

Atlas Notifications consumes normalized events.

It does not own the domain workflows that produce those events. In particular,
request notification delivery remains fully decoupled from
`MediaRequestService`, request persistence, and Jellyseerr provider operations.

The request service publishes normalized request events. The Notifications
module independently subscribes, formats, routes, and delivers them.

```text
MediaRequestService
        |
        | normalized request.* event
        v
Atlas Runtime Bus
        |
        v
Notifications Processor
        |
        +--> Formatter
        +--> Router
        +--> Discord Adapter
        +--> Generic Webhook Adapter
```

## Runtime Bus subscription

The module subscribes to:

```text
atlas.health-changed
atlas.health-report
storage.threshold-crossed
storage.threshold-recovered
movie.*
tv.*
anime-movie.*
anime-tv.*
sports.*
request.*
```

## Media Request lifecycle events

Supported request events are:

```text
request.created
request.submitted
request.pending
request.approved
request.searching
request.downloading
request.importing
request.available
request.rejected
request.failed
request.cancelled
```

### Severity

| Event | Severity |
| --- | --- |
| `request.available` | `success` |
| `request.failed` | `warning` |
| `request.rejected` | `warning` |
| `request.cancelled` | `warning` |
| Other `request.*` events | `info` |

`request.available` is presented as **Ready to Watch**.

### Routing

Request events are routed using normalized `payload.media_type`.

| Media type | Route | Environment variable |
| --- | --- | --- |
| `movie` | `movies` | `ATLAS_NOTIFICATIONS_DISCORD_MOVIES_WEBHOOK` |
| `tv` | `tv` | `ATLAS_NOTIFICATIONS_DISCORD_TV_WEBHOOK` |
| `anime_movie` | `anime_movies` | `ATLAS_NOTIFICATIONS_DISCORD_ANIME_MOVIES_WEBHOOK` |
| `anime_tv` | `anime_tv` | `ATLAS_NOTIFICATIONS_DISCORD_ANIME_TV_WEBHOOK` |
| Unknown | `system` | `ATLAS_NOTIFICATIONS_DISCORD_SYSTEM_WEBHOOK` |

### Notification context

Request notifications may include:

- media title;
- release year;
- media type;
- season number;
- request status;
- provider;
- Atlas request ID;
- availability timestamp.

User-specific Discord mentions are intentionally not implemented. They belong
to the later user notification preference and Discord identity contracts.

## Configuration

Discord routing uses the following environment variables:

```text
ATLAS_NOTIFICATIONS_DISCORD_SYSTEM_WEBHOOK
ATLAS_NOTIFICATIONS_DISCORD_MOVIES_WEBHOOK
ATLAS_NOTIFICATIONS_DISCORD_TV_WEBHOOK
ATLAS_NOTIFICATIONS_DISCORD_ANIME_MOVIES_WEBHOOK
ATLAS_NOTIFICATIONS_DISCORD_ANIME_TV_WEBHOOK
ATLAS_NOTIFICATIONS_DISCORD_SPORTS_WEBHOOK
ATLAS_NOTIFICATIONS_DISCORD_TIMEOUT
```

Generic webhook delivery uses:

```text
ATLAS_NOTIFICATIONS_WEBHOOK_URL
ATLAS_NOTIFICATIONS_WEBHOOK_TIMEOUT
```

Secrets must remain in the module's local `.env` file and must never be
committed.

## Processing

Process pending events once:

```bash
modules/notifications/scripts/process.sh
```

Run the persistent worker:

```bash
modules/notifications/scripts/worker.sh
```

## Verification

Run module verification:

```bash
modules/notifications/scripts/verify.sh
```

Run focused request-notification tests:

```bash
python -m pytest tests/core/test_request_notifications.py -q
```

The verification contract checks module structure, Compose configuration,
Sports formatting, request notification documentation, request formatting,
request routing, Ready to Watch behavior, and request context.
