# ADR 0008 — Atlas Portal Architecture

## Status

Accepted

## Scope

This ADR establishes the long-term architecture for the Atlas web
applications.

It defines the responsibilities and boundaries between:

- Atlas Portal
- Atlas API
- Atlas Core

Future architecture decisions may extend this design but should not redefine
these responsibility boundaries without explicitly superseding this ADR.

## Context

Project Atlas requires a public web portal that provides a unified user
experience across identity, media, requests, favorites, sports, health,
documentation, and administration.

Atlas already has a Python domain layer containing identity, policy,
retention, cleanup, scheduler, event, provider, and health contracts. The
portal must expose those capabilities without duplicating domain behavior or
placing infrastructure credentials in the browser.

The application will be self-hosted through the existing Docker and Caddy
infrastructure at:

https://atlas.shadowinc.co

## Decision

Atlas will use a two-application web architecture:

1. A Next.js application for the user interface.
2. A FastAPI application for the HTTP API.

The applications will be deployed as separate Docker containers.

Caddy will expose both applications through one public origin:

- Portal routes will be served by Next.js.
- `/api/v1/*` routes will be served by FastAPI.

The FastAPI service will import and coordinate the existing `atlas` Python
package. Domain behavior will remain in Atlas core rather than being copied
into HTTP route handlers.

## Frontend

The portal frontend will use:

- Next.js
- App Router
- TypeScript
- Tailwind CSS
- Atlas-owned reusable components
- Server and client components where appropriate

The frontend is responsible for presentation, navigation, user interaction,
and calling the Atlas API.

The frontend must not contain service API keys, infrastructure credentials,
or authorization decisions that are not independently enforced by the API.

## Backend

The API will use:

- FastAPI
- Pydantic contracts
- Existing Atlas core services
- Versioned routes under `/api/v1`
- Dependency-based authentication and authorization

The API is responsible for:

- Authentication
- Session lifecycle
- Authorization
- Input validation
- Core service coordination
- Provider error normalization
- Event publication
- HTTP response contracts

## Authentication

The browser portal will use server-managed sessions.

After successful authentication, the browser will receive an opaque session
identifier in a cookie configured with:

- HttpOnly
- Secure
- SameSite=Lax
- A bounded expiration

Session state will be stored server-side and may be revoked by Atlas.

Browser credentials and session identifiers must not be stored in
`localStorage`.

Token-based authentication may be added later for machine clients without
changing the browser session model.

## Authorization

Atlas will initially support the existing roles:

- admin
- user

The API is the authorization boundary.

The frontend may hide controls and navigation based on the current user's
role, but every protected operation must also be authorized by the API.

## Application Boundaries

The Next.js portal owns:

- Page rendering
- Navigation
- Forms and user interaction
- Loading, empty, and error states
- Role-aware presentation

The FastAPI service owns:

- HTTP contracts
- Authentication and sessions
- Role enforcement
- Atlas core coordination
- Secret handling
- Provider communication

Atlas core continues to own:

- Identity
- Invitations
- Favorites
- Policy
- Retention
- Cleanup
- Scheduler
- Events
- Health
- Provider contracts

## Repository Layout

Portal applications will be placed under:

```text
apps/
├── portal/
└── api/
