# Maintainerr Cleanup Safety

## Status

Maintainerr is deployed as an optional Project Atlas operational service, but
destructive automatic cleanup is disabled for the v1.0 safety baseline.

Production validation during M-023.20 found no configured Maintainerr
collections, collection-media rows, rule groups, or rules.

## Atlas Authorization Boundary

A cleanup recommendation is not deletion authorization.

Atlas Policy owns protection state such as user favorites. Retention converts
that state into normalized eligibility, and Cleanup converts eligibility into
recommendations. The current Atlas cleanup execution boundary is dry-run only
and uses provider delete previews rather than destructive mutation.

Maintainerr must not bypass that boundary with independently configured delete,
unmonitor, or request-removal actions.

See:

- [Automatic Cleanup Safety](architecture/AUTOMATIC_CLEANUP_SAFETY.md)
- [ADR 0018 — Cleanup Mutation Authorization](ADR/0018-cleanup-mutation-authorization.md)

## Favorite Protection

M-023.20 cross-boundary tests prove:

```text
favorite
  -> Atlas policy protection
  -> retention ineligible
  -> cleanup KEEP
  -> execution SKIPPED
  -> provider preview not called
```

Removing the final favorite allows a later fresh assessment to change
eligibility. An older cleanup recommendation does not become destructive
authorization.

## Current Supported Operation

Atlas supports inspection and non-destructive cleanup planning through its
cleanup commands. The full workflow remains preview-only.

Examples:

```bash
atlas cleanup scan jellyfin --json
atlas cleanup execute jellyfin --dry-run --json
atlas cleanup run jellyfin --dry-run --json
atlas cleanup history --json
```

`atlas cleanup run` may persist audit events to the configured Atlas cleanup
audit log. Those events describe preview activity and cannot claim that media
was modified.

## Destructive Maintainerr Rules

Do not enable destructive Maintainerr collections or rules for the v1.0 safety
baseline.

The earlier 72-hour concept of directly performing actions such as:

- deleting files;
- unmonitoring Sonarr or Radarr items; or
- removing Jellyseerr requests

is not an approved production path until every destructive candidate can be
freshly authorized by Atlas immediately before mutation.

Configuration-only favorite exclusions are insufficient because protection
state belongs to Atlas and may change after a cleanup candidate was selected.

## Future Destructive Automation

Before destructive automatic cleanup can be enabled, the mutation path must:

1. normalize the provider and item identity;
2. obtain fresh Atlas policy and retention authorization;
3. require authorization identity to match the mutation target;
4. deny protected, review-required, unavailable, or ambiguous state;
5. use an explicitly destructive provider capability;
6. durably audit authorization and mutation outcome; and
7. reconcile ambiguous provider outcomes rather than blindly retrying them.

Until those requirements are implemented and production-validated, preserving
media is the correct fail-closed behavior.
