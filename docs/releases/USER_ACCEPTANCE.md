# Atlas User Acceptance

**Document Status:** Approved
**Applies To:** Atlas v1.0 and later
**Document Owner:** Project Atlas Engineering
**Last Updated:** 2026-08-02

---

# 1. Purpose

## 1.1 Objective

This document defines the formal User Acceptance Certification process for
Project Atlas.

Its purpose is to verify that Atlas delivers a complete, reliable, and
understandable experience for both end users and administrators before a
release may be certified.

Unlike automated testing, User Acceptance Certification evaluates the product
from the perspective of the people who will actually use it.

---

# 2. Acceptance Philosophy

Atlas is considered complete only when users can successfully perform the
critical workflows required by the product.

Passing automated tests is necessary but does not replace human validation.

User experience is a release requirement.

Critical workflows must be understandable, predictable, and free from dead
ends.

---

# 3. Test Environment

User Acceptance testing should be performed against an environment that closely
matches the intended production deployment.

The environment should include:

- Atlas Portal
- Jellyfin
- Jellyseerr
- Sonarr
- Radarr
- Prowlarr
- qBittorrent
- Homepage
- Dozzle
- Supporting Atlas services

Representative user accounts should be available for testing.

---

# 4. Test Roles

The following roles participate in User Acceptance Certification.

## End User

Validates the day-to-day Atlas experience.

## Administrator

Validates operational workflows and routine administration.

## Reviewer

Confirms recorded results and approves certification.

---

# 5. Test Recording

Each workflow uses the same certification template.

Required fields:

- Workflow
- Priority
- Validation Type
- Preconditions
- Steps
- Expected Result
- Observed Result
- Pass / Fail
- Reviewer
- Date
- Notes

---

# 6. End-User Journeys

## 6.1 Invitation Acceptance

### Workflow

Invitation Acceptance

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Valid invitation exists.
- Invitation has not expired.

### Steps

1. Open the invitation.
2. Verify the correct Atlas page loads.
3. Review invitation information.
4. Continue to registration.

### Expected Result

The invitation is understandable, valid, and directs the user into the Atlas
registration workflow.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.2 Registration

### Workflow

Account Registration

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Valid invitation exists.

### Steps

1. Complete the registration form.
2. Submit the form.
3. Verify account creation.
4. Continue to sign in.

### Expected Result

The user successfully creates an Atlas account with clear feedback and no
unexpected errors.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.3 Sign In

### Workflow

User Sign In

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Valid user account exists.

### Steps

1. Navigate to the sign-in page.
2. Enter credentials.
3. Authenticate.

### Expected Result

The user reaches the Atlas Portal with a valid authenticated session.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.4 Dashboard

### Workflow

Portal Dashboard

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- User is signed in.

### Steps

1. Open the dashboard.
2. Review navigation.
3. Review available actions.
4. Verify page responsiveness.

### Expected Result

The dashboard provides a clear starting point with consistent navigation and
discoverable primary actions.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.5 Media Discovery

### Workflow

Media Discovery

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- User is signed in.
- Media services are available.

### Steps

1. Open the media discovery experience.
2. Browse available media categories.
3. Open a representative media item.
4. Review available details and actions.

### Expected Result

The user can understand available media, open a media item, and identify the
next supported action without backend knowledge.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.6 Media Search

### Workflow

Media Search

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- User is signed in.
- Search provider is available.

### Steps

1. Open media search.
2. Enter a representative title.
3. Submit the search.
4. Review results.
5. Open the intended result.

### Expected Result

Search returns understandable results, loading and empty states are visible,
and the user can select the intended media item without confusion.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.7 Media Request

### Workflow

Media Request Submission

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- User is signed in.
- The selected media item is eligible for request.

### Steps

1. Open the media detail view.
2. Select the request action.
3. Confirm the request if required.
4. Review the submission result.
5. Open the user's request list or status view.

### Expected Result

The request is submitted once, confirmation is clear, and the resulting request
status is visible to the user. Duplicate or stale eligibility must not produce a
second provider submission, and an outcome-ambiguous mutation must not be
silently retried.

### Series and Anime Acceptance Requirement

Atlas v1.0 must also validate the implemented television and anime-series
explicit-season request journey in the production runtime.

Certification requires:

- the Portal exposes truthful per-season availability/requestability and fails
  closed when that state is unknown or ineligible;
- the user explicitly chooses one intended positive season scope rather than a
  generic, all-seasons, or inferred current-season action;
- the Portal derives standard TV versus anime TV from server-provided
  classification rather than browser title/genre inference;
- television and anime-series requests reach the appropriate supported
  downstream automation path;
- the production request path runs on the repository-approved Seerr runtime,
  not the legacy deployed Jellyseerr image;
- the migrated standard-TV and anime-TV Sonarr service IDs match Atlas's
  server-owned routing configuration;
- `monitorNewItems=all` is verified on both supported Seerr Sonarr services;
- an ongoing requested series can remain monitored through Seerr and Sonarr or
  Sonarr Anime so newly released episodes can be acquired automatically under
  the configured monitoring, quality, and release rules; and
- the user is not required to create a new Atlas request for every future
  episode of an already monitored ongoing series.

The monitoring policy is service-owned. Season scope selected by the user is
Atlas Request state; `monitorNewItems` is not a caller-controlled Request field
and must not be presented as a per-request toggle.

The source-level explicit-season TV/anime workflow was subsequently exercised
through controlled production E2.5 acceptance. The repository-pinned Seerr
runtime was deployed under maintenance, backup, rollback, and deployment-lock
control. Post-migration validation confirmed server-owned standard-TV and
anime-TV routing and service-level `monitorNewItems=all` ownership.

The passing Anime-TV acceptance used Demon Slayer: Kimetsu no Yaiba Season 2.
Atlas persisted `media_type=anime_tv`; Seerr request `3` used server `1`; the
series appeared only in `sonarr-anime` under `/media/Anime TV`; Season 2 was
monitored; and standard Sonarr remained free of the Anime target.

A prior Mushoku Tensei acceptance attempt exposed a routing-harness defect,
failed closed, and was reconciled without media loss. That attempt is retained
as recovery evidence and is not counted as the passing Anime-TV case.

### Observed Result

E2.5 production acceptance passed.

- Controlled Jellyseerr-to-Seerr migration completed under the Atlas deployment
  transaction.
- Standard-TV and Anime-TV provider routing were revalidated after migration.
- `monitorNewItems=all` was verified as service-owned downstream policy.
- Standard-TV acceptance remained valid.
- Demon Slayer: Kimetsu no Yaiba Season 2 was submitted as `anime_tv`.
- Seerr routed the request to server `1`.
- Anime Sonarr owned the resulting target at
  `/media/Anime TV/Demon Slayer - Kimetsu no Yaiba`.
- Anime Sonarr reported `seriesType=anime`.
- Season 2 remained monitored.
- Standard Sonarr had zero Demon Slayer matches after submission.
- Atlas Doctor and the final fail-closed transaction guard passed.

Closure evidence:

`8a974fb51ff1f0d8651cf4e17f0f36a430cb1de63b50bebfdc0201ca4f79e385`

### Pass / Fail

**PASS — E2.5 TV / Anime production request routing and ongoing-series
monitoring acceptance.**

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.8 Request Status

### Workflow

Request Status Tracking

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- User has at least one submitted request.

### Steps

1. Open the request-status experience.
2. Locate the submitted request.
3. Review its current state.
4. Refresh or revisit the view after a state change.

### Expected Result

The request state is understandable, current, and consistent with the supported
backend workflow.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.9 Favorites

### Workflow

Favorite Management

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- User is signed in.
- A media item is available to favorite.

### Steps

1. Add the media item to favorites.
2. Confirm the visual favorite state.
3. Open the user's favorites view.
4. Confirm the media item appears.
5. Remove the media item from favorites.
6. Confirm it no longer appears as favorited.

### Expected Result

Favorite state changes are immediate, understandable, persistent, and
consistent across the Portal.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.10 Protected Media

### Workflow

Protected-Media Behavior

### Priority

Critical

### Validation Type

Combined

### Preconditions

- User is signed in.
- A favorite is linked to supported protection behavior.

### Steps

1. Add a media item to favorites.
2. Confirm its protected state where surfaced.
3. Review the user's favorites or protection information.
4. Remove the item from favorites.
5. Confirm the protection state updates consistently.

### Expected Result

The user can understand that favoriting protects applicable media and that
removing the favorite updates the corresponding protection state.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.11 Playback Handoff

### Workflow

Jellyfin Playback Handoff

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- User is signed in.
- The selected media item is available in Jellyfin.
- Jellyfin access is configured.

### Steps

1. Open an available media item in Atlas.
2. Select the supported playback action.
3. Confirm the correct Jellyfin destination opens.
4. Verify the intended media item is available.
5. Return to Atlas.

### Expected Result

The transition from Atlas to Jellyfin is clear, reliable, and does not require
the user to understand the underlying service relationship.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 6.12 Sign Out

### Workflow

User Sign Out

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- User is signed in.

### Steps

1. Locate the sign-out action.
2. Sign out.
3. Attempt to open a protected Portal route.
4. Verify authentication is required again.

### Expected Result

The session ends, protected content is no longer accessible, and the resulting
destination is clear.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

# 7. Administrator Journeys

## 7.1 Administrator Sign In

### Workflow

Administrator Sign In

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Valid administrator account exists.

### Steps

1. Open the administrator sign-in page.
2. Enter valid administrator credentials.
3. Authenticate.
4. Open an administrator-only route.

### Expected Result

The administrator reaches the supported administrative experience, and
administrator-only routes remain unavailable to unauthorized users.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 7.2 Invitation Management

### Workflow

Administrator Invitation Management

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Administrator is signed in.

### Steps

1. Create an invitation.
2. Review invitation details and expiration.
3. Confirm the invitation can be used.
4. Revoke a second invitation.
5. Confirm the revoked invitation is rejected.

### Expected Result

Invitation creation, inspection, expiration, use, and revocation are clear,
reliable, and correctly authorized.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 7.3 User Management

### Workflow

Administrator User Management

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Administrator is signed in.
- Representative user accounts exist.

### Steps

1. Open the user list.
2. Open a user detail view.
3. Review identity and account status.
4. Activate or suspend a supported account.
5. Assign or change a supported role.
6. Confirm the resulting state.

### Expected Result

The administrator can inspect and manage supported user state safely, with
clear consequences and correct authorization.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 7.4 Request Management

### Workflow

Administrator Request Management

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Administrator is signed in.
- At least one representative request exists.

### Steps

1. Open the request queue.
2. Open a request detail view.
3. Review request state and requester information.
4. Approve, reject, or otherwise resolve the request where supported.
5. Confirm the new state is visible to the user.

### Expected Result

The administrator can understand and resolve supported requests, and resulting
state changes remain consistent across administrator and user views.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 7.5 Media Management

### Workflow

Routine Media Operations

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Administrator is signed in.
- Supported media operations are available.

### Steps

1. Open the supported media administration area.
2. Inspect representative media state.
3. Perform an approved routine media operation.
4. Review success or failure feedback.
5. Confirm state consistency afterward.

### Expected Result

Routine media administration is clear, authorized, and possible without
unsupported direct backend interaction.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 7.6 Health Dashboard

### Workflow

System and Service Health Review

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Administrator is signed in.
- Health providers are available.

### Steps

1. Open the health dashboard.
2. Review overall system health.
3. Review individual service health.
4. Review storage state.
5. Review recent significant failures.
6. Identify the next reasonable action for a representative failure.

### Expected Result

The administrator can understand current operational state and identify a
reasonable next action without first using the CLI.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 7.7 Module Visibility

### Workflow

Module Status Visibility

### Priority

Important

### Validation Type

Manual + Runtime

### Preconditions

- Administrator is signed in.
- At least one optional module is installed or disabled.

### Steps

1. Open module status.
2. Review installed, enabled, disabled, and unhealthy states.
3. Open representative module detail where available.
4. Confirm unsupported mutations are not presented.

### Expected Result

The administrator can understand module availability and health within the
supported administrative boundary.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

## 7.8 Routine Operations Without CLI

### Workflow

Routine Administration Without CLI

### Priority

Critical

### Validation Type

Manual + Runtime

### Preconditions

- Administrator is signed in.
- Representative daily administrative tasks are available.

### Steps

1. Create or revoke an invitation.
2. Review a user.
3. Review or resolve a request.
4. Inspect media state.
5. Inspect system and service health.
6. Review module status.
7. Complete the session without opening a shell.

### Expected Result

Routine administration can be completed through supported Atlas interfaces.
The CLI remains reserved for advanced diagnostics, recovery, development, and
documented exceptional operations.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

# 8. Accessibility and Responsiveness

## Accessibility Review

- [ ] Primary workflows are keyboard accessible where supported.
- [ ] Focus state is visible.
- [ ] Form labels are clear.
- [ ] Validation errors are associated with the relevant control.
- [ ] Critical status does not rely only on color.
- [ ] Text remains readable at supported zoom levels.
- [ ] Interactive controls have understandable names.
- [ ] Navigation order is logical.

## Responsive Review

- [ ] Sign-in and registration work on supported small screens.
- [ ] Dashboard remains usable on supported small screens.
- [ ] Media discovery and search remain usable.
- [ ] Request submission remains usable.
- [ ] Favorites remain usable.
- [ ] Administrator workflows remain usable at supported sizes.
- [ ] No critical action is hidden or inaccessible.
- [ ] Horizontal overflow does not block critical use.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

# 9. Performance Experience

Representative workflows should respond within a range that feels reliable and
does not cause users to repeat actions unnecessarily.

Validate:

- [ ] Sign-in provides timely feedback.
- [ ] Dashboard loading provides visible progress.
- [ ] Search provides visible progress.
- [ ] Request submission prevents accidental duplicate action.
- [ ] Outcome-ambiguous Request submission is not automatically retried.
- [ ] Ongoing TV/anime monitoring acquires future episodes without per-episode
      Atlas requests once the supported series-request workflow is enabled.
- [ ] Favorites update without misleading delay.
- [ ] Administrator lists and details remain responsive.
- [ ] Health data loads within an acceptable operational window.
- [ ] Slow providers produce visible, understandable states.
- [ ] Timeouts provide actionable feedback.
- [ ] No critical workflow appears frozen.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

# 10. Failure and Recovery Experience

Validate representative failures for:

- invalid invitation;
- expired invitation;
- invalid credentials;
- suspended or disabled account;
- unavailable identity provider;
- unavailable media provider;
- request conflict or duplicate request;
- unavailable Jellyfin target;
- failed favorite update;
- unavailable health provider;
- network interruption;
- session expiration.

For each failure:

- [ ] The failure is visible.
- [ ] The message is understandable.
- [ ] The next action is clear.
- [ ] User input is preserved where practical.
- [ ] No misleading success is shown.
- [ ] Retry behavior is safe.
- [ ] The workflow does not end in an unexplained dead end.
- [ ] Administrative detail is not exposed to ordinary users.

### Observed Result

______________________________________________

### Pass / Fail

______________________________________________

### Reviewer

______________________________________________

### Date

______________________________________________

### Notes

______________________________________________

---

# 11. Defect Classification

Acceptance findings use the following severity levels.

## Critical

A critical defect blocks a required journey, threatens security or data
integrity, creates misleading success, or prevents safe operation.

Critical defects block release.

## High

A high-severity defect causes a major workflow failure or requires unsupported
backend intervention for routine use.

High-severity defects normally block release unless explicitly handled under
the Release Policy.

## Medium

A medium-severity defect causes confusion, inconsistency, or a recoverable
workflow problem without preventing the overall journey.

Medium findings must be resolved or explicitly accepted.

## Low

A low-severity defect is a minor usability, wording, or visual issue that does
not prevent successful use.

Low findings may be deferred when documented.

## Acceptance Finding Record

For every defect, record:

- identifier;
- workflow;
- severity;
- description;
- reproduction steps;
- expected behavior;
- observed behavior;
- owner;
- resolution;
- retest result;
- disposition.

---

# 12. Certification Summary

## Environment

- **Atlas Version:** _______________________________________________
- **Branch:** _____________________________________________________
- **Commit:** _____________________________________________________
- **Environment:** ________________________________________________
- **Test Start Date:** ____________________________________________
- **Test Completion Date:** _______________________________________

## Journey Results

- **Critical End-User Journeys Passed:** ___________________________
- **Critical Administrator Journeys Passed:** ______________________
- **Accessibility Result:** _______________________________________
- **Responsive Result:** __________________________________________
- **Performance Result:** _________________________________________
- **Failure and Recovery Result:** _________________________________

## Defect Summary

- **Critical Open:** ______________________________________________
- **High Open:** __________________________________________________
- **Medium Open:** ________________________________________________
- **Low Open:** ___________________________________________________

## Certification Decision

- [ ] Approved
- [ ] Rejected
- [ ] Deferred pending corrective work

## Certification Notes

~~~text
______________________________________________________________________
______________________________________________________________________
______________________________________________________________________
~~~

---

# 13. Approval

User Acceptance Certification is approved only when:

- all critical end-user journeys pass;
- all critical administrator journeys pass;
- no critical defect remains open;
- high-severity defects are resolved or explicitly handled under policy;
- accepted limitations are documented;
- results are evidence-based;
- the project owner or authorized maintainer approves the result.

## Approval Record

- **Project Owner or Authorized Maintainer:** ______________________
- **Recorded Approval:** __________________________________________
- **Date:** _______________________________________________________
- **Notes:** ______________________________________________________

---

# 14. References

This document is governed and supported by:

- [`README.md`](README.md);
- [`V1_RELEASE_PLAN.md`](V1_RELEASE_PLAN.md);
- [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md);
- [`../governance/ENGINEERING_CHARTER.md`](../governance/ENGINEERING_CHARTER.md);
- [`../governance/DEVELOPMENT_WORKFLOW.md`](../governance/DEVELOPMENT_WORKFLOW.md);
- [`../governance/TESTING_STANDARD.md`](../governance/TESTING_STANDARD.md);
- [`../governance/DOCUMENTATION_STANDARD.md`](../governance/DOCUMENTATION_STANDARD.md);
- [`../governance/RELEASE_POLICY.md`](../governance/RELEASE_POLICY.md);
- [`../../ROADMAP.md`](../../ROADMAP.md);
- [`../../CHANGELOG.md`](../../CHANGELOG.md);
- [`../BUILD_LOG.md`](../BUILD_LOG.md).

---

# Acceptance Completion

This document is complete only when:

- every critical journey has been executed;
- expected and observed results are recorded;
- defects are classified;
- critical failures are resolved;
- accepted limitations are documented;
- certification is approved;
- the repository records the result.

Planned validation, incomplete notes, or assumed success do not satisfy User
Acceptance Certification.

## M-018.30 — Read-Only Service Lifecycle API Foundation

M-018.30 establishes the backend read-only Service Lifecycle transport required
for the administrator health/service-visibility journey. Authorized
administrators can now be served normalized managed-service collection/detail,
aggregate health, and infrastructure-summary data through
`GET /api/v1/services`, `GET /api/v1/services/{service_identifier}`,
`GET /api/v1/services/health`, and `GET /api/v1/services/summary`, guarded by
`system.health.read`.

This backend certification does **not** certify the Portal experience itself.
The health/service-visibility journey remains open until the Administration
Portal consumes these contracts and representative user-acceptance validation
is completed. M-018.30 introduces no lifecycle mutation.

## M-018.31 — Portal Service Lifecycle Foundation

M-018.31 implements the first Administration Portal consumer of the read-only
Service Lifecycle API. Authorized administrators with `system.health.read` can
open `/portal/services` and receive managed-service overview cards, aggregate
service-health presentation, and read-only individual service details.

The Portal consumes production-shaped Atlas API responses: managed-service
identity is joined with aggregate runtime and health entries, the `unavailable`
health state is preserved, and detail inspection is enriched with normalized
overview runtime/health state. No lifecycle mutation control is exposed.

Engineering validation for this slice is complete: focused Service
Lifecycle/navigation tests passed 23 tests, the complete Portal suite passed
218 tests across 27 files, and typecheck, formatting, lint, whitespace,
bounded-remote, and Atlas Doctor checks passed.

This closes the implementation prerequisite for the managed-service overview,
service health cards, and service detail views. It does **not** by itself
complete User Acceptance Certification. Representative administrator journey
execution, responsive phone/tablet validation, touch interaction, mobile-safe
layout validation, remaining lifecycle presentation surfaces, and final v1.0
approval remain open.

## M-018.32 — Responsive & Mobile Service Lifecycle Acceptance

M-018.32 completes the engineering acceptance prerequisite for responsive
phone/tablet Service Lifecycle presentation. The existing responsive Portal
architecture and auto-fitting managed-service card grid are retained; shared
retry interaction is explicitly touch-sized, and long Service Lifecycle
identifiers/detail values are permitted to wrap rather than forcing critical
horizontal overflow.

The Service Lifecycle experience remains read-only. No restart, update,
rollback, stop, start, or other lifecycle mutation control is introduced.

Progressive Web App support was evaluated after responsive validation. No
tracked Portal PWA runtime owner exists, so PWA implementation is deferred
beyond v1.0 and the responsive authenticated Portal remains the supported v1.0
mobile administration experience.

This milestone closes the responsive phone/tablet, touch-friendly lifecycle,
mobile-safe service-card/table, and PWA-evaluation implementation/presentation
gates. It does **not** mark the broader Responsive Review checklist above as
complete and does **not** constitute final User Acceptance Certification.
Representative administrator journey execution, Update Availability,
Maintenance History, and final v1.0 approval remain open.
