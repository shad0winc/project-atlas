# Project Atlas Build Log

## 2026-11-04 — Sports Proxy rollout and maintenance verification

- Verified Proxmox boot ordering after a graceful shutdown. The media pool was ready before CT100 started, the storage watcher reported healthy, and Docker and the Atlas API recovered.
- Rehearsed the rollout in maintenance. The first controller failed readiness and rolled back. Corrected traversal permissions on the staged source and verified all 38 pinned files as the container's runtime user.
- Activated the controller-only publication `baseline-sports-proxy-profile-7455a793428d`. Verified administrator console access and regular-user denial with maintenance enabled.
- Observed the Sports writer recover after a refresh failure. The portal and writer both confirmed the empty Premier League schedule for Nov. 4. Recurrence remains open.
- Followed Bucks–Celtics for private live acceptance. Playback and session release remain to be verified.
- Ran 27 metadata refresh and 7 isolated maintenance recovery tests successfully. The maintenance-control suite passed 16 checks, with its Unix-socket transport test blocked by workspace permissions.

See the [Sports Proxy deployment checkpoint](docs/operations/SPORTS_PROXY_PROFILE.md) for operational details.

## Earlier build history

-------------------------------------------------------------------------------
Production HTTPS Deployment
-------------------------------------------------------------------------------

Status:
    COMPLETE

Achievements:

✓ Public DNS configured
✓ AT&T IP Passthrough validated
✓ UniFi WAN public IP verified
✓ Public HTTP ingress operational
✓ Automatic HTTPS enabled
✓ Let's Encrypt certificate issued
✓ HTTP/2 enabled
✓ HTTP/3 enabled
✓ Automatic certificate renewal configured
✓ Security headers enabled
✓ Modular Caddy architecture deployed

Validation:

✓ HTTPS certificate trusted
✓ External accessibility confirmed
✓ HTTP redirects to HTTPS
✓ Core regression suite passed

Atlas URL:

https://atlas.shadowinc.co

-------------------------------------------------------------------------------

<!-- PORTAL-ARCHITECTURE-BUILD-START -->

-------------------------------------------------------------------------------
Atlas Portal Architecture Design
-------------------------------------------------------------------------------

Status:
    COMPLETE

Milestone:
    M-019 — Atlas Portal

Decisions:

✓ Next.js selected for the portal frontend
✓ FastAPI selected for the Atlas API
✓ Existing Atlas core retained as the domain layer
✓ Single public origin retained at atlas.shadowinc.co
✓ API namespace defined as /api/v1
✓ Caddy designated as the public routing boundary
✓ Server-managed session authentication selected
✓ API-enforced role authorization defined
✓ Frontend, API, and core responsibilities documented
✓ Initial vertical delivery scope defined

Planned Application Layout:

    apps/portal
    apps/api
    stack/portal.yml

Initial Delivery Scope:

    API health endpoint
    Login and logout
    Current-session lookup
    Protected portal layout
    Portal home
    System status
    Administrative user listing

Documentation:

    Portal architecture ADR
    docs/architecture/PORTAL.md
    ROADMAP.md
    README.md
    CHANGELOG.md

Next Engineering Step:

    Scaffold the FastAPI service and implement its health contract.

-------------------------------------------------------------------------------

<!-- PORTAL-ARCHITECTURE-BUILD-END -->

-------------------------------------------------------------------------------
Atlas API Foundation
-------------------------------------------------------------------------------

Status:
    COMPLETE

Milestone:
    M-019 — API Foundation

Achievements:

✓ FastAPI application scaffolded
✓ Versioned API routing established
✓ Stable /api/v1/health contract implemented
✓ Contract tests added
✓ Docker image created
✓ Docker health check implemented
✓ Local container validation completed
✓ Core regression suite passed

Validation:

✓ API tests: 3/3 PASS
✓ Atlas core tests: 541/541 PASS
✓ Docker build successful
✓ Docker runtime validated
✓ Health endpoint verified

Next Step:

    Scaffold the Atlas Portal (Next.js) application.

-------------------------------------------------------------------------------

