# ADR-0006 - Separate Anime Services

## Status

Accepted

## Date

2026-07-03

## Decision

Anime TV and anime movies will be managed by dedicated Sonarr and Radarr instances.

## Context

Anime often has different naming conventions, release groups, metadata behavior, quality expectations, and indexers than standard TV and movies.

## Alternatives Considered

- Use the existing Sonarr and Radarr instances for anime
- Create separate anime-specific instances

## Consequences

### Benefits

- Cleaner automation
- Separate quality profiles
- Easier troubleshooting
- Better future flexibility

### Tradeoffs

- Two additional containers
- Slightly more configuration

## Outcome

Accepted.
