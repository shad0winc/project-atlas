
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
