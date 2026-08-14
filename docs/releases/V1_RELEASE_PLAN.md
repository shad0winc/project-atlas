# Atlas v1.0 Release Plan

**Document Status:** Approved
**Release:** v1.0.0
**Milestone:** M-022.1
**Document Owner:** Project Atlas Engineering
**Last Updated:** 2026-08-02

---

# 1. Purpose

## 1.1 Objective

This document defines the contractual scope, engineering objectives, release
criteria, and execution plan for Project Atlas version 1.0.

Unlike the project roadmap, this document is not intended to capture every
future capability or engineering idea. Instead, it defines the minimum
complete product that must exist before Atlas may be considered ready for a
production release.

The Atlas v1.0 Release Plan serves as the authoritative engineering reference
for all remaining work leading to the initial public release.

---

## 1.2 Scope of this Document

This document establishes:

- the Atlas v1.0 product vision;
- the approved release scope;
- release philosophy;
- engineering principles;
- release blockers;
- acceptance criteria;
- user experience requirements;
- release validation requirements;
- the definition of release success.

This document does not replace the project roadmap, governance framework, or
engineering standards. It builds upon them.

---

## 1.3 Relationship to Other Documentation

This release plan works together with the following permanent repository
documents:

- Engineering Charter
- Development Workflow
- Coding Standards
- Testing Standard
- Documentation Standard
- ADR Policy
- Release Policy
- Roadmap
- Changelog
- Build Log

Together these documents define how Atlas is engineered, validated,
documented, and ultimately released.

---

# 2. Vision

## 2.1 Product Vision

Project Atlas v1.0 is a self-hosted media platform designed for friends and
family that provides a unified experience for discovering, requesting,
managing, and enjoying media while giving administrators a centralized,
maintainable platform for operating the entire environment.

Atlas does not attempt to replace the specialized applications that power the
platform.

Instead, Atlas coordinates those services into a cohesive product with a
consistent user experience, governance model, operational framework, and
administrative interface.

---

## 2.2 Release Vision

Atlas v1.0 represents the smallest complete version of the platform that
delivers a stable, maintainable, and enjoyable experience for both end users
and administrators.

Features that do not materially improve that objective are intentionally
deferred beyond the initial release.

---

## 2.3 Long-Term Vision

Atlas is intended to evolve through incremental releases.

Future versions may expand the platform with additional modules,
administrative capabilities, analytics, gaming infrastructure, and other
services without compromising the stability of the core platform established
by v1.0.

---

# 3. Release Philosophy

Atlas releases follow the engineering philosophy established throughout the
project.

The release process values quality over schedule and operational confidence
over feature quantity.

The following principles govern every Atlas release.

## Stability Over Novelty

New functionality must never compromise an otherwise stable platform.

## Reliability Over Convenience

Engineering decisions prioritize predictable operation, repeatable deployment,
and operational confidence.

## Documentation Before Release

Every user-visible capability must be documented before release.

Documentation is considered part of the product.

## Validation Before Publication

No feature is complete until it has been validated through the engineering,
operational, and user acceptance processes.

## Repository as the Source of Truth

The Git repository represents the authoritative state of the Atlas project.

Documentation, implementation, release history, and engineering decisions are
maintained together.

## User Experience as a Release Requirement

Technical correctness alone is insufficient.

Atlas must provide an intuitive, consistent, and reliable experience for both
end users and administrators.

---

# 4. Product Definition

Atlas v1.0 provides a unified platform built upon proven services and
supported by a governed engineering framework.

## 4.1 End Users

Atlas v1.0 provides:

- Secure account management
- Unified Atlas Portal
- Jellyfin integration
- Media discovery
- Media request workflow
- Favorites management
- Protected media support
- User profile management
- Consistent navigation
- Reliable media access

The platform should require no knowledge of the underlying infrastructure.

---

## 4.2 Administrators

Atlas v1.0 provides:

- User management
- Invitation management
- Request management
- Media operations
- Health visibility
- Service visibility
- Module management
- Operational dashboards
- Documented maintenance procedures

Routine platform administration should be achievable through the Atlas Portal
without requiring direct command-line interaction for normal operations.

---

# 5. Scope Boundaries

Maintaining release discipline requires clearly defining both what is included
and what is intentionally excluded from Atlas v1.0.

## 5.1 Included in v1.0

Atlas v1.0 includes all functionality required to provide a stable,
maintainable, and complete media platform experience for friends and family.

This includes:

- User onboarding
- Authentication
- Media requests
- Favorites
- Protected media
- Administrative management
- Health monitoring
- Release governance
- Engineering governance
- Operational documentation

---

## 5.2 Deferred Beyond v1.0

The following capabilities are intentionally deferred:

- Advanced analytics
- Predictive operational intelligence
- Extended notification systems
- Gaming server hosting
- Experimental feature modules
- Enterprise-focused capabilities

Deferral does not indicate cancellation.

These capabilities remain candidates for future releases.

---

# 6. Non-Goals

Atlas v1.0 intentionally does not attempt to:

- replace every underlying service interface;
- become a general-purpose homelab management platform;
- implement every planned roadmap feature;
- optimize for enterprise-scale deployments;
- prioritize experimentation over reliability.

The objective is to deliver a complete and dependable first release.

---

# 7. Release Principles

Every remaining engineering sprint leading to Atlas v1.0 shall follow these
principles.

1. Every sprint removes at least one release blocker.
2. Every sprint produces a reviewable repository artifact.
3. Every sprint concludes with validation.
4. Every sprint concludes with a clean repository state.
5. Every sprint concludes with a commit and push.
6. Features may be deferred to protect release quality.
7. User experience is considered a release requirement.
8. Engineering quality is never sacrificed for schedule.
9. The approved release scope remains locked unless a major release risk is
   identified.
10. Atlas v1.0 ships only when the release criteria defined by this document
    have been satisfied.

---

# 8. Release Blockers

Atlas v1.0 may not be released while any applicable critical release blocker
remains unresolved.

The following items define the approved release-blocker scope.

## 8.1 Administration Portal

The Administration Portal must support the routine workflows required to
operate Atlas without direct command-line access.

Required capabilities include:

- administrator authentication;
- administrative dashboard;
- user listing and user detail;
- user activation and deactivation;
- role management;
- invitation creation and revocation;
- request queue visibility;
- request review and approval where applicable;
- routine media operations;
- sports operations within the implemented v1.0 scope;
- module status visibility;
- system and service health visibility;
- storage visibility;
- recent operational failure visibility.

Advanced analytics, predictive recommendations, and experimental administrative
automation do not block v1.0.

## 8.2 End-User Portal

The end-user Portal must support a complete and understandable user journey.

Required capabilities include:

- invitation acceptance;
- account creation;
- authentication;
- sign-in and sign-out;
- clear session behavior;
- dashboard access;
- media discovery;
- media search;
- media requests;
- request confirmation;
- request status visibility;
- favorites management;
- protected-media behavior;
- Jellyfin access or playback handoff;
- clear success, empty-state, validation, and failure feedback.

A technically functional workflow that remains confusing, inconsistent, or
unreliable is not considered complete.

## 8.3 User Onboarding

A first-time user must be able to complete onboarding without administrator
intervention beyond issuing the invitation.

Onboarding must provide:

- clear invitation instructions;
- understandable account requirements;
- actionable validation messages;
- clear completion feedback;
- a direct path to sign in;
- a successful transition into the Atlas Portal.

## 8.4 Core Media Workflow

The complete request lifecycle must be validated:

1. Discover or search for media.
2. Select the intended item.
3. Submit the request.
4. Receive clear confirmation.
5. View the request and its current status.
6. Complete any required administrative approval.
7. Confirm that available media can be opened through the supported experience.

The workflow must avoid duplicate submissions, ambiguous status, and silent
failure.

For television and anime series, the supported Portal must make season scope
explicit. The implemented source path exposes one positive season at a time,
uses Atlas-normalized fail-closed requestability, and derives standard TV versus
anime TV from server-provided classification. A generic TV action must not
silently interpret an unspecified season as an all-seasons request, and the
Portal does not expose all-seasons or inferred current-season shortcuts.

At source checkpoint `ad84a30d`, this explicit-season Portal workflow is
implemented. That source milestone does not certify the production request path.
When a user requests a supported ongoing series, the v1.0 workflow must still
preserve downstream monitoring through Seerr and the appropriate Sonarr instance
so future episodes can be acquired automatically under the configured
monitoring, quality, and release rules without requiring a new Atlas request per
episode.

### 8.4.1 Seerr Monitoring and Migration Gate

**Status: PASSED under E2.5 production acceptance.**

Series-request certification requires the canonical Seerr runtime rather than
the legacy Jellyseerr image. E2.5 completed that controlled production
migration to the repository-pinned Seerr v3.4.1 runtime.

The production gate completed the required controls:

1. pre-change Seerr/Jellyseerr configuration and rollback evidence were
   preserved;
2. the migration ran inside Atlas maintenance and deployment-lock control;
3. post-migration standard-TV and anime-TV service identities were revalidated
   against Atlas's server-owned routing configuration;
4. `monitorNewItems=all` was verified for both supported Sonarr services;
5. Atlas API/provider connectivity and request preflight were reverified after
   migration; and
6. controlled production acceptance exercised both the retained standard-TV
   path and the Anime-TV path.

The passing Anime-TV acceptance used Demon Slayer: Kimetsu no Yaiba Season 2.
Atlas persisted `media_type=anime_tv`, Seerr routed provider request `3` to
server `1`, Anime Sonarr created the target under `/media/Anime TV` with
`seriesType=anime`, Season 2 remained monitored, and standard Sonarr had zero
matching targets after submission.

The preceding Mushoku Tensei acceptance attempt exposed a routing-harness
defect. It failed closed and was explicitly reconciled without media loss; it
is recovery/hardening evidence rather than the passing Anime-TV case.

`monitorNewItems` remains Seerr Sonarr-service policy. Atlas Request season
scope remains explicit user-selected Request state and must not be represented
as a caller-controlled future-monitoring toggle.

Passing this gate closes the production Seerr migration, post-migration route
verification, service-level monitoring verification, and TV/anime
ongoing-series acceptance requirements. It does not by itself close the
remaining release-candidate, broader journey, accessibility, performance,
sustained-use, pilot, stabilization, or final v1.0 approval gates.

# 9. Acceptance Criteria

Atlas v1.0 is eligible for release only when every applicable acceptance
criterion has been satisfied.

## 9.1 Engineering Acceptance

- [ ] Approved v1.0 scope is implemented.
- [ ] Public contracts are deterministic and documented.
- [ ] Model, service, provider, CLI, API, and Portal boundaries remain clear.
- [ ] Compatibility paths are preserved or migration is documented.
- [ ] Focused tests pass.
- [ ] Relevant subsystem regression tests pass.
- [ ] Full repository regression tests pass.
- [ ] Machine-readable output is parsed and contract-checked.
- [ ] Runtime validation passes for supported executable interfaces.
- [ ] No known release-blocking engineering defects remain.

## 9.2 Repository Acceptance

- [ ] The working branch contains only intentional work.
- [ ] `git diff --check` passes.
- [ ] Staged changes are reviewed explicitly.
- [ ] Temporary exports, generators, caches, and review artifacts are excluded.
- [ ] The repository contains no exposed credentials or secrets.
- [ ] Version sources are synchronized.
- [ ] The release commit is focused and reviewable.
- [ ] The working tree is clean after the release commit.
- [ ] The release tag points to the certified commit.

## 9.3 Operational Acceptance

- [ ] Supported services start successfully.
- [ ] Required containers report healthy or expected status.
- [ ] Storage is mounted, writable, and has acceptable capacity.
- [ ] VPN-dependent traffic follows the approved network boundary.
- [ ] Hardware acceleration works where supported.
- [ ] Backup creation has been validated.
- [ ] Recovery or restoration guidance has been reviewed.
- [ ] Service diagnostics provide actionable information.
- [ ] Common administrator operations are documented.
- [ ] Rollback or recovery expectations are documented.

## 9.4 Documentation Acceptance

- [ ] Architecture documentation matches implementation.
- [ ] Public API documentation is current.
- [ ] CLI documentation is current.
- [ ] Portal and user documentation are current.
- [ ] Installation and configuration guidance are current.
- [ ] Upgrade and migration guidance are current.
- [ ] Backup and recovery guidance are current.
- [ ] `ROADMAP.md` accurately reflects release scope.
- [ ] `CHANGELOG.md` accurately records notable changes.
- [ ] `docs/BUILD_LOG.md` records completed implementation and validation.
- [ ] Release notes are complete.
- [ ] Release certification is complete.
- [ ] Local documentation links validate.

## 9.5 Security Acceptance

- [ ] Authentication behavior has been validated.
- [ ] Authorization and role boundaries have been validated.
- [ ] Sensitive values are not exposed in logs, APIs, CLI output, or artifacts.
- [ ] Mutation paths require the intended authorization.
- [ ] User and operational data are handled safely.
- [ ] Dependency and configuration risks have been reviewed.
- [ ] No unresolved security issue blocks supported use.

## 9.6 User Experience Acceptance

- [ ] A first-time user can understand and accept an invitation.
- [ ] Account creation is clear and reliable.
- [ ] Sign-in and sign-out behavior are clear and reliable.
- [ ] Navigation is consistent.
- [ ] Media discovery and search are understandable.
- [ ] Media requests provide clear confirmation and status.
- [ ] Favorites are easy to add, view, and remove.
- [ ] Protected-media behavior is understandable.
- [ ] Jellyfin or playback handoff is clear.
- [ ] Empty states and errors provide useful guidance.
- [ ] Critical workflows have no dead ends.
- [ ] Representative workflows perform acceptably.
- [ ] User Experience Certification is approved.

## 9.7 Administrator Experience Acceptance

- [ ] An administrator can sign in securely.
- [ ] Invitations can be created and revoked.
- [ ] Users and roles can be reviewed and managed.
- [ ] Requests can be reviewed and resolved.
- [ ] Routine media operations are available.
- [ ] System, service, storage, and failure state are visible.
- [ ] Modules can be inspected within the supported boundary.
- [ ] Routine administration does not require direct CLI use.
- [ ] Failures provide actionable guidance.
- [ ] Administrator Experience Certification is approved.

---

# 10. Release Validation Matrix

The release validation matrix connects technical correctness with the experience
observed by users and administrators.

| Area | Technical validation | Experience validation | v1.0 requirement |
| --- | --- | --- | --- |
| Invitation | Invitation contract, lifecycle, expiration, and authorization pass | Invitation is understandable and opens the correct onboarding path | Required |
| Registration | Account creation, validation, identity linking, and errors pass | A first-time user can complete registration without confusion | Required |
| Sign-in | Authentication, sessions, authorization, and sign-out pass | Sign-in is clear, responsive, and reliable | Required |
| Portal | Routes, APIs, state handling, and permissions pass | Navigation is consistent and critical actions are discoverable | Required |
| Media discovery | Provider and API results validate | Users can browse and understand available media | Required |
| Search | Query, normalization, results, and errors validate | Users can find intended media efficiently | Required |
| Requests | Submission, deduplication, status, approval, and errors pass | Users receive clear confirmation and can track progress | Required |
| Favorites | Add, list, remove, serialization, and persistence pass | Favorite state is obvious and manageable | Required |
| Protection | Policy, retention, cleanup, and ownership contracts pass | Users understand how favorites affect protection | Required |
| Playback handoff | Supported Jellyfin target and access behavior validate | Users can move from Atlas to playback without uncertainty | Required |
| User administration | User, role, status, and invitation operations pass | Routine user management is clear and safe | Required |
| Request administration | Queue, decision, authorization, and status changes pass | Administrators can resolve requests efficiently | Required |
| Health visibility | System, service, storage, and failure contracts pass | Administrators can identify current operational problems | Required |
| Core notifications | Event production, delivery state, and errors validate | Users receive essential workflow feedback | Required |
| Backup and recovery | Backup artifacts and recovery procedures validate | Administrators can understand and execute recovery | Required |
| Upgrade | Version, migration, compatibility, and rollback validate | Upgrade guidance is understandable and reproducible | Required |
| Advanced analytics | Existing behavior remains safe when absent | Not required for the core experience | Deferred |
| Predictive operations | Existing behavior remains safe when absent | Not required for the core experience | Deferred |
| Gaming infrastructure | No unsupported dependency is introduced | Outside the Atlas v1.0 product boundary | Future vision |

---

# 11. User Experience Certification

User Experience Certification verifies that Atlas v1.0 is understandable,
reliable, and comfortable to use for its intended audience.

Passing technical tests is necessary but does not, by itself, certify the
experience.

Certification must be performed using representative accounts and supported
runtime services.

## 11.1 Certification Method

Each critical journey must record:

- workflow name;
- priority;
- validation type;
- preconditions;
- steps performed;
- expected result;
- observed result;
- pass or fail;
- defects or usability notes;
- reviewer;
- date.

Priority values are:

- **Critical** — required for v1.0;
- **Important** — expected unless explicitly deferred;
- **Optional** — does not block v1.0.

Validation types are:

- **Automated**;
- **Manual**;
- **Combined**;
- **Planned**.

A critical workflow may not be marked complete based only on planned validation.

## 11.2 End-User Certification

The following end-user journeys are critical.

### Invitation

A user receives a valid invitation and understands how to begin registration.

Certification requires:

- the invitation reaches the intended user;
- the link opens the correct Atlas destination;
- expiration and invalid-state feedback are clear;
- instructions are understandable;
- no backend knowledge is required.

### Account Creation

A first-time user creates an Atlas account successfully.

Certification requires:

- required fields are clear;
- validation messages are actionable;
- invalid input does not lose unrelated valid input unnecessarily;
- completion feedback is clear;
- the next action is obvious.

### Sign-In

A registered user signs in and reaches the intended Portal destination.

Certification requires:

- credential failures are understandable;
- successful sign-in is responsive;
- session behavior is predictable;
- protected routes remain protected;
- sign-out works clearly.

### Dashboard

The user reaches a useful starting point after authentication.

Certification requires:

- primary actions are discoverable;
- current requests and relevant media state are understandable;
- empty states are informative;
- navigation remains consistent.

### Media Discovery and Search

The user can browse or search for intended media.

Certification requires:

- results are understandable;
- unavailable or empty results provide useful feedback;
- loading and error states are visible;
- media details support an informed request decision.

### Media Request

The user submits a valid request and understands the result.

Certification requires:

- the request action is discoverable;
- duplicate or ineligible requests are handled clearly;
- successful submission produces confirmation;
- status is visible afterward;
- failures provide actionable feedback;
- outcome-ambiguous mutations are not automatically replayed;
- television/anime season scope is explicit before series mutation;
- unknown or ineligible per-season requestability fails closed to no mutation;
- the Portal uses server-provided classification for standard TV versus anime TV;
- no generic, all-seasons, or inferred current-season shortcut bypasses the
  explicit-season scope;
- the production request path uses the repository-approved Seerr runtime;
- both supported Sonarr services have `monitorNewItems=all` verified after
  migration; and
- ongoing requested series can remain monitored so future episodes are acquired
  automatically without requiring per-episode Atlas requests.

### Favorites and Protection

The user can add and remove favorites and understand their effect.

Certification requires:

- favorite state changes visibly;
- personal favorites are easy to find;
- protected-media behavior is explained where applicable;
- removing a favorite updates the state consistently;
- no stale or contradictory state remains.

### Playback Handoff

The user can open available media through the supported Jellyfin experience.

Certification requires:

- the handoff target is clear;
- available media opens correctly;
- unavailable media does not present a misleading action;
- returning to Atlas remains understandable.

### Sign-Out

The user can end the session intentionally.

Certification requires:

- sign-out is discoverable;
- the session is invalidated;
- protected content is no longer accessible;
- the resulting destination is clear.

## 11.3 Administrator Certification

The following administrator journeys are critical.

### Administrator Sign-In

An authorized administrator signs in and reaches the administrative experience.

### Invitation Management

The administrator can:

- create an invitation;
- inspect invitation state;
- revoke an invitation;
- understand expiration and failure states.

### User Management

The administrator can:

- list users;
- inspect user detail;
- activate or deactivate supported accounts;
- manage supported roles;
- understand the impact of administrative actions.

### Request Administration

The administrator can:

- view the request queue;
- inspect request details;
- approve, reject, or otherwise resolve supported requests;
- understand the resulting status;
- identify failures.

### Media Operations

The administrator can perform the routine media operations included in the
approved v1.0 scope without using unsupported direct backend actions.

### Health and Service Visibility

The administrator can inspect:

- overall health;
- service health;
- storage state;
- recent significant failures.

The experience must help identify the next reasonable action.

### Module Visibility

The administrator can inspect module status and understand whether optional
capabilities are available, disabled, or unhealthy.

### Routine Operation Without CLI

Representative daily administration must be achievable through supported Portal
workflows.

The CLI remains available for advanced diagnostics, recovery, development, and
documented exceptional operations.

## 11.4 Certification Failure

User Experience Certification fails when a critical journey contains:

- a dead end;
- silent failure;
- misleading success;
- unclear required action;
- inaccessible critical control;
- inconsistent state;
- unsupported backend dependency for routine use;
- unacceptable reliability or response behavior.

Failures must be recorded and resolved or explicitly classified under the
Release Policy before certification may pass.

## 11.5 Certification Approval

User Experience Certification is approved only when:

- all critical journeys pass;
- important defects are resolved or explicitly accepted;
- results are recorded;
- the end-user experience is reviewed;
- the administrator experience is reviewed;
- the project owner or authorized maintainer approves the result.

---

# 12. Definition of Success

Atlas v1.0 succeeds when it delivers the smallest complete product that users
can trust and administrators can maintain.

## 12.1 End-User Success

A first-time user can:

1. Receive and understand an invitation.
2. Create an account.
3. Sign in.
4. Reach the Atlas Portal.
5. Discover or search for media.
6. Submit a media request.
7. Understand and track request status.
8. Add and remove favorites.
9. Understand protected-media behavior.
10. Open available media through Jellyfin.
11. Sign out.

The user does not need to understand Docker, Proxmox, command-line tools, or
the individual backend services.

## 12.2 Administrator Success

An administrator can:

1. Sign in securely.
2. Create and revoke invitations.
3. Review and manage users and roles.
4. Review and resolve supported requests.
5. Perform approved routine media operations.
6. Inspect system, service, storage, and failure state.
7. Inspect module status.
8. Follow documented backup, recovery, and upgrade procedures.
9. Complete routine administration without direct CLI use.

## 12.3 Engineering Success

The project:

- preserves stable public contracts;
- passes required automated and runtime validation;
- maintains accurate documentation;
- provides reproducible operational procedures;
- contains no unresolved release blocker;
- satisfies release certification;
- remains clean, reviewable, and supportable.

## 12.4 Release Success

The release:

- is correctly versioned;
- is committed and pushed;
- is tagged correctly;
- includes complete release notes;
- includes known limitations;
- includes upgrade and recovery guidance;
- passes post-release validation;
- accurately represents the software users receive.

---

# 13. Release Sequence

The approved path to Atlas v1.0 is:

## Phase 1 — Release Engineering Foundation

Create and approve:

- `docs/releases/README.md`;
- `docs/releases/V1_RELEASE_PLAN.md`;
- `docs/releases/RELEASE_CHECKLIST.md`;
- `docs/releases/USER_ACCEPTANCE.md`;
- `docs/releases/RELEASE_TEMPLATE.md`;
- `docs/releases/RELEASE_NOTES_TEMPLATE.md`.

## Phase 2 — Administration Portal Foundation

Complete the supported Portal architecture, navigation, authentication,
authorization, state handling, error handling, and core layout.

## Phase 3 — User Administration

Complete invitation, user, role, activation, and account-management workflows.

## Phase 4 — Media and Request Operations

Complete supported media discovery, search, request, request-administration,
favorites, protection, and playback-handoff workflows.

## Phase 5 — Health Dashboard

Complete system, service, storage, module, and recent-failure visibility required
for routine administration.

## Phase 6 — Core Notifications

Complete essential invitation, request, media-availability, and administrative
failure notifications.

## Phase 7 — User Experience Certification

Execute and record all critical end-user and administrator journeys.

## Phase 8 — Release Readiness

Complete:

- regression testing;
- runtime validation;
- security review;
- compatibility review;
- backup and recovery review;
- upgrade validation;
- documentation review;
- release checklist;
- release certification.

## Phase 9 — Release

Complete:

- final version update;
- release commit;
- annotated or signed release tag where supported;
- release notes;
- publication;
- post-release validation.

Only after these phases pass may Atlas be published as `v1.0.0`.

---

# 14. References

This plan is governed and supported by:

- [`README.md`](README.md);
- [`../governance/ENGINEERING_CHARTER.md`](../governance/ENGINEERING_CHARTER.md);
- [`../governance/DEVELOPMENT_WORKFLOW.md`](../governance/DEVELOPMENT_WORKFLOW.md);
- [`../governance/CODING_STANDARDS.md`](../governance/CODING_STANDARDS.md);
- [`../governance/TESTING_STANDARD.md`](../governance/TESTING_STANDARD.md);
- [`../governance/DOCUMENTATION_STANDARD.md`](../governance/DOCUMENTATION_STANDARD.md);
- [`../governance/ADR_POLICY.md`](../governance/ADR_POLICY.md);
- [`../governance/VERSIONING_AND_CONTRIBUTING.md`](../governance/VERSIONING_AND_CONTRIBUTING.md);
- [`../governance/RELEASE_POLICY.md`](../governance/RELEASE_POLICY.md);
- [`../../ROADMAP.md`](../../ROADMAP.md);
- [`../../CHANGELOG.md`](../../CHANGELOG.md);
- [`../BUILD_LOG.md`](../BUILD_LOG.md).

The dedicated release checklist, user-acceptance guide, templates, and final
certification records will be linked as they are completed.

---

# Release-Plan Completion

This release plan is complete when:

- all sections are approved;
- release scope is locked;
- blockers and acceptance criteria are explicit;
- user experience is a formal release gate;
- the release sequence is approved;
- repository validation passes;
- the document is committed and pushed.

Approval of this plan does not certify Atlas v1.0.

It establishes the contract against which Atlas v1.0 will be implemented,
validated, and certified.

## M-018.30 — Read-Only Service Lifecycle API Foundation

M-018.30 establishes the read-only Service Lifecycle API foundation for the
service-visibility portion of the v1.0 administrator requirement. The API
exposes managed-service collection/detail, aggregate health, and infrastructure
summary through four GET-only endpoints protected by `system.health.read`.

This closes the backend Service Lifecycle transport prerequisite; it does not
certify the administrator Portal experience. Portal presentation and final
health/service-visibility user acceptance remain required for v1.0. Guarded
lifecycle mutation remains outside the v1.0 read-only boundary.

## M-018.31 — Portal Service Lifecycle Foundation

M-018.31 closes three implementation gates in the v1.0 administrator
service-visibility path: managed-service overview, service health cards, and
service detail views.

The protected `/portal/services` experience consumes the four M-018.30 GET-only
Service Lifecycle endpoints through the authenticated Portal service boundary
and remains protected by `system.health.read`. Runtime and health presentation
are aligned with the production aggregate payloads, including unavailable
health and normalized read-only detail enrichment.

This milestone does not close the complete administrator acceptance gate.
Update-availability indicators, Maintenance History presentation, responsive
phone/tablet acceptance, touch-friendly lifecycle interaction, mobile-safe
service-card/table acceptance, PWA evaluation, representative user acceptance,
and final v1.0 approval remain required. Guarded lifecycle mutation remains
outside the v1.0 read-only boundary.

## M-018.32 — Responsive & Mobile Service Lifecycle Acceptance

M-018.32 closes the responsive/mobile presentation prerequisites for the
read-only Administration Portal Service Lifecycle experience. The implementation
reuses the Portal's existing responsive architecture and shared dashboard grid,
adds explicit touch-target hardening to the shared retry interaction, and
protects Service Lifecycle cards and read-only detail values from narrow-screen
overflow.

The managed-service presentation remains card-based and the detail surface
remains semantic/read-only. No mobile-only route, duplicate lifecycle
presentation architecture, lifecycle mutation control, or artificial table was
introduced.

Progressive Web App support was evaluated after responsive validation. Atlas has
no tracked Portal manifest, service worker, Workbox integration, install prompt,
or other PWA runtime owner. PWA implementation is therefore deferred beyond
v1.0; the responsive authenticated Portal is the supported v1.0 mobile
administration experience.

M-018.32 closes the responsive phone/tablet, touch-friendly lifecycle,
mobile-safe service-card/table, and PWA-evaluation ROADMAP gates. Update
Availability presentation, Maintenance History presentation, representative
administrator User Acceptance, and final v1.0 approval remain required. Guarded
lifecycle mutation remains outside the v1.0 read-only boundary.
