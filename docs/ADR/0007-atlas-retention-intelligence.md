# ADR 0007 - Atlas Retention Intelligence

## Status

Accepted

## Context

Project Atlas needs a safe, predictable, and user-aware retention system for media lifecycle management.

Automatic deletion is high impact, so retention behavior must be documented before implementation.

## Decision

Atlas will introduce Atlas Retention Intelligence, or ARI.

ARI defines retention behavior for movies, TV, anime movies, and anime TV.

## Retention Rules

### Rule 1 - Watched Media

If media is watched to completion, it becomes eligible for cleanup after 72 hours.

### Rule 2 - Stale Media

If media remains unwatched for 30 days, it becomes eligible for cleanup.

### Rule 3 - Favorites

If a user favorites media, that media becomes protected from automatic cleanup.

Favorites must not move or duplicate media files.

Favorited media should be exposed through a user-specific favorites view, collection, shortcut, or metadata-based link.

Unfavoriting media removes the protection rule and removes the item from the user's favorites view.

### Rule 4 - Disliked Media

If a user dislikes media, it becomes eligible for cleanup after 24 hours.

## Safety Requirements

Media must not be deleted if:

- It is currently downloading.
- It is currently importing.
- It is marked as favorite or protected.
- Its retention timer has not expired.
- The rule match is uncertain.

## Principle

When uncertain, Atlas keeps the media.

## Implementation Notes

Maintainerr is the preferred first implementation path.

Future Atlas automation may expand ARI with user-specific views, favorite shortcuts, dislike-triggered removal queues, and dashboard visibility.

## Consequences

Atlas gains automated lifecycle management while preserving user control and safety.

Favorites become metadata-driven protection, not separate storage.
