# Project Atlas User Guide

**Document Status:** D.3B v1.0 Documentation Candidate
**Applies To:** Project Atlas v1.0 end-user experience
**Audience:** Friends, family, and other authorized Atlas users
**Canonical Repository Path:** `docs/guides/USER_GUIDE.md`

---

## 1. Purpose

Project Atlas provides one user-facing Portal for the supported v1.0 media and
Sports experience.

This guide explains how an ordinary Atlas user can:

- accept an invitation and register;
- sign in and sign out;
- use the Portal dashboard;
- discover and search for Media;
- request movies, television, and anime;
- review personal request status;
- manage Favorites;
- understand protection associated with Favorites;
- open available Media through the supported playback experience;
- use supported Sports workflows;
- understand maintenance, provider outages, and safe retry guidance.

Routine Atlas use should not require direct access to Docker, Proxmox, Seerr,
Sonarr, Radarr, qBittorrent, Caddy, the Atlas CLI, or other backend services.

---

## 2. What Atlas v1.0 Is for

Atlas v1.0 is designed as a dependable friends-and-family Media and Sports
platform.

For end users, the supported experience includes:

- secure account access;
- a unified Atlas Portal;
- Media discovery and search;
- Media requests;
- Favorites;
- protected-media behavior where applicable;
- request status visibility;
- supported availability notifications;
- Media playback handoff;
- Sports discovery/request workflows;
- access to completed Sports recordings where supported;
- supported personal account settings;
- clear failure and maintenance states.

Some future Atlas capabilities are intentionally outside v1.0. A missing future
feature should not require users to bypass Atlas and operate infrastructure
directly.

---

## 3. Getting Access

### 3.1 Invitations

Atlas registration begins with a valid invitation.

When you receive an invitation:

1. open the invitation using the link or instructions provided by the Atlas
   administrator;
2. confirm that the Atlas registration experience loads;
3. review the invitation information;
4. continue to registration.

An expired, revoked, invalid, or already-used invitation may no longer permit
registration. If Atlas reports that the invitation cannot be used, contact the
administrator rather than repeatedly resubmitting it.

Treat an invitation as a private credential. Do not post or publicly share it.

### 3.2 Registration

Complete the registration form using the information requested by Atlas.

After successful registration, continue to the sign-in experience.

If registration fails, review the message shown by Atlas. Do not assume an
account was created unless Atlas confirms success.

---

## 4. Signing In

Open the Atlas sign-in page and enter your Atlas credentials.

A successful sign-in takes you into the authenticated Atlas Portal.

If Atlas rejects the credentials:

- verify the username and password;
- correct any obvious input error;
- try again only when the message indicates that retry is appropriate;
- contact the administrator if the account appears unavailable, disabled, or
  repeatedly fails with valid credentials.

Atlas does not require ordinary users to manage API tokens or backend provider
credentials.

---

## 5. The Portal Dashboard

The Portal dashboard is the normal starting point after sign-in.

Use the Portal navigation to move among the user-facing experiences available
to your account, such as:

- Dashboard;
- Media;
- Requests;
- Favorites;
- Sports;
- supported profile/account surfaces.

The exact options you see can depend on your permissions and on which optional
Atlas capabilities are enabled.

A missing permission should not be worked around by opening backend service
interfaces directly.

---

## 6. Media Discovery

Media Discovery lets you browse Media through Atlas without needing to know
which backend service owns the content.

From the Media experience you can:

1. browse available categories or discovery results;
2. open a Media item;
3. review the details Atlas provides;
4. identify whether the item is already available, requestable, unavailable, or
   otherwise requires a different next action.

Atlas may show different information depending on provider availability and the
Media type.

If a required provider is unavailable, Atlas should show an unavailable/error
state rather than pretending that there are simply no results.

---

## 7. Media Search

Use Media Search when you already know what you want to find.

A normal search flow is:

1. open Media Search;
2. enter a title;
3. submit the search;
4. review the returned results;
5. open the intended item.

Atlas distinguishes among loading, empty, and failure states.

An empty result means Atlas successfully completed the search but did not find a
matching item.

An unavailable or error state means the search could not be completed
reliably. Use the retry action when Atlas offers one.

---

## 8. Available Media and Playback

When Media is already available, Atlas should present the supported action for
opening or watching it.

Atlas may hand playback to the supported Jellyfin experience.

The handoff should be clear, and unavailable Media should not present a
misleading playback action.

After playback, return to Atlas using the normal browser or application
navigation.

Users should not need Jellyfin administration access to use the supported
playback workflow.

---

## 9. Requesting Movies

When a movie is eligible for request and your account has permission to create
requests, Atlas presents a Request action.

A normal movie request flow is:

1. open the movie in Media Discovery or Search;
2. review its availability and request state;
3. choose the Request action;
4. review the result;
5. open **Your requests** to follow the request status.

Atlas protects against duplicate active requests. If the same logical Media
target already has an active request, Atlas may tell you it is already
requested rather than creating another provider submission.

Do not repeatedly click or refresh a request action while Atlas is processing
it.

---

## 10. Requesting Television and Anime

### 10.1 Explicit season selection

Atlas v1.0 uses explicit-season requests for television and anime series.

When a series is requestable:

1. open the series;
2. review the seasons Atlas displays;
3. choose one specific eligible season;
4. submit the request;
5. review the resulting status.

Atlas does not expose a generic "request all seasons" or inferred
"current-season" shortcut in the supported Portal workflow.

If Atlas cannot determine whether a season is requestable, the safe behavior is
to withhold the Request action or report that availability is unavailable.

### 10.2 Future episodes of an ongoing series

Your Atlas request describes the season you intentionally selected.

Downstream Media automation may continue monitoring an ongoing requested series
for future episodes according to the server's configured monitoring, quality,
and release rules.

This means you should not need to create a new Atlas request for every future
episode of an already monitored ongoing series.

The monitoring policy is controlled by Atlas and its server-side Media
services; ordinary users do not choose backend server IDs or monitoring flags.

---

## 11. Your Requests

Use the personal Requests experience to review your Atlas request history and
current states.

Requests can move through different lifecycle states as Atlas and its Media
provider process them.

Depending on the request, you may see states representing concepts such as:

- pending or submitted;
- processing;
- available;
- rejected;
- failed;
- cancelled;
- recovery or reconciliation required.

The exact presentation is owned by Atlas.

A successfully empty request history is different from a request-provider
failure. Atlas should not represent an outage as "you have no requests."

---

## 12. Request Failures and Safe Retry Behavior

Not every failed-looking request should be immediately repeated.

### 12.1 Safe retry

For read-only loading failures, Atlas may offer **Try again** or another clear
refresh action.

Using that retry is appropriate when the Portal explicitly offers it.

### 12.2 Already requested

If Atlas tells you the title or season is already requested, do not try to
create duplicate requests through another account or backend service.

Review **Your requests** or contact an administrator if the existing request
state appears incorrect.

### 12.3 Outcome unconfirmed or reconciliation required

A network or provider failure can sometimes occur after Atlas has begun a
request operation but before Atlas can prove the provider result.

In that situation, Atlas may tell you to:

- check **Your requests**;
- refresh the current request state;
- avoid retrying immediately; or
- contact an administrator.

If Atlas explicitly says **Do not retry this request**, follow that instruction.

Atlas intentionally blocks blind automatic replay because the provider action
may already have happened.

---

## 13. Cancelling Requests

Where cancellation is supported, Atlas evaluates the current request state
before allowing the action.

After a cancellation attempt, review the resulting request status.

If Atlas reports that cancellation requires reconciliation or tells you not to
retry, do not repeatedly submit the cancellation. Refresh the request state and
follow the guidance shown.

A failed cancellation does not necessarily prove that the external provider
left the request unchanged.

---

## 14. Favorites

Favorites are personal Atlas relationships that make selected Media easier to
find.

When the feature is available, you can:

- add Media to Favorites;
- view your personal Favorites;
- remove a Favorite.

The visible Favorite state should update consistently after a successful
change.

If Atlas cannot load Favorites, it should show an error state rather than an
empty Favorites list.

---

## 15. Favorites and Media Protection

Favorites can participate in Atlas protection rules.

Where protection applies, favoriting Media tells Atlas that the Media should be
protected from applicable automated cleanup behavior.

Removing the Favorite updates that relationship and the corresponding
protection state.

Favoriting is not the same as making a second copy of the Media. The underlying
Media can remain in the shared library while Atlas maintains the user's
personal Favorite relationship.

If the Favorite or protection state looks inconsistent after an error, refresh
the Atlas view before repeating a mutation.

---

## 16. Sports

Atlas v1.0 includes supported Sports workflows when the Sports module is enabled
for your deployment and account.

The user-facing Sports experience may include:

- viewing supported events;
- submitting supported Sports requests or subscriptions;
- reviewing current Sports state;
- accessing completed Sports recordings where available.

If Sports is unavailable, Atlas should present an explicit failure state rather
than silently erasing previously known events or recordings.

Provider failure does not automatically mean that an existing Sports
subscription or recording has been cancelled.

If the Sports page reports an error, use the provided retry action when
appropriate or contact the administrator.

---

## 17. Availability and Notifications

Atlas can expose request availability through the request lifecycle and
supported notification paths.

When a requested item becomes available, use the Atlas request state and
supported notification you receive to determine the next action.

Notification delivery depends on the notification capability configured by the
administrator. A missing notification does not necessarily mean the request
state failed to update.

When in doubt, check **Your requests** directly.

Extended notification features beyond the supported v1.0 paths may belong to
future Atlas releases.

---

## 18. Account and Profile Behavior

Use Atlas account/profile surfaces for settings that the Portal explicitly
supports.

Your available options depend on the implemented v1.0 account experience and
your permissions.

Do not use backend provider account pages to change Atlas-owned identity,
permissions, or request ownership unless an administrator specifically directs
you to do so.

Contact an administrator for:

- account activation or deactivation issues;
- role or permission changes;
- invitation problems;
- identity-link problems;
- settings not exposed through the supported Portal.

---

## 19. Signing Out

Use the Portal's sign-out action when you are finished using Atlas on a shared
or untrusted device.

A successful sign-out ends the Atlas session and removes access to protected
Portal content.

After signing out, protected pages should require authentication again.

Do not rely on simply closing a browser tab as the normal sign-out procedure.

---

## 20. Maintenance Mode

Atlas administrators may temporarily place the public Portal and API into
maintenance mode during planned production work.

During maintenance:

- the Portal or API may report that Atlas is temporarily unavailable;
- normal user traffic may receive HTTP 503 Service Unavailable;
- a retry interval may be provided;
- backend services may still be healthy even though public access is
  intentionally paused.

Maintenance is not the same as your account being deleted or your requests
being erased.

Wait until the maintenance window has ended and try again.

Do not attempt to bypass maintenance by opening internal backend services.

---

## 21. Provider Outages and Degraded Service

Atlas depends on several external or local provider services.

A provider can be unavailable while the Atlas Portal itself remains reachable.

Examples of user-visible degraded behavior can include:

- Media search unavailable;
- Media libraries unavailable;
- Requests unavailable;
- season availability unavailable;
- Sports unavailable;
- playback target unavailable.

Atlas intentionally distinguishes provider failure from valid empty data.

Previously known durable state, such as an existing request or Sports
subscription, should not be assumed deleted merely because a provider is
temporarily unavailable.

---

## 22. Understanding Error Messages

Atlas v1.0 aims to make user-facing failures understandable and actionable.

Common patterns include:

### "Try again"

The failed operation is read-only or otherwise safe to refresh using the action
Atlas provides.

### "Unavailable"

Atlas cannot currently obtain reliable information from the required service.
This is different from an empty list.

### "Already requested"

An active request already owns the logical Media target. Review existing request
status instead of creating another request.

### "Check requests"

Atlas cannot safely confirm the result of a request mutation. Review **Your
requests** before taking another action.

### "Do not retry"

Atlas has detected an outcome that requires reconciliation. Repeating the
mutation could create an unsafe duplicate or conflicting provider action.

Follow the message and contact an administrator when needed.

---

## 23. What Users Should Not Need to Do

Normal Atlas use should not require you to:

- run shell commands;
- use the Atlas CLI;
- sign in to Docker or Proxmox;
- manage Caddy;
- open Seerr, Sonarr, Radarr, Prowlarr, or qBittorrent administration;
- edit `.env` files;
- manage API keys;
- select provider server IDs;
- manually alter request state files;
- bypass authorization;
- retry a mutation after Atlas says not to retry.

If a routine user journey appears to require one of these actions, contact the
administrator.

---

## 24. When to Contact an Administrator

Contact the Atlas administrator when:

- you cannot use a valid invitation;
- registration repeatedly fails;
- valid credentials no longer work;
- your account appears disabled;
- a permission or role seems incorrect;
- a request remains in a reconciliation-required state;
- a cancellation remains unresolved;
- Media or Sports remains unavailable after the provider recovers;
- a Favorite/protection state remains inconsistent after refresh;
- expected Media is unavailable for an extended period;
- maintenance appears to remain active beyond the planned window;
- you need a setting not exposed through your supported Portal experience.

When reporting a problem, describe:

- what page you were using;
- what action you attempted;
- the user-facing error message;
- whether you already used a Portal-provided retry;
- the approximate time of the problem.

Do not send passwords, invitation tokens, access tokens, API keys, or other
credentials with a support report.

---

## 25. Privacy and Security Basics

Use Atlas as a private authenticated service.

For your own account:

- keep your password private;
- do not share invitation links or invitation secrets publicly;
- sign out on shared devices;
- do not copy authentication tokens from browser tools;
- do not send credentials in screenshots or support messages;
- report suspicious access to the administrator.

Atlas may retain operational and security audit evidence, but credentials should
not appear in those records.

---

## 26. Quick User Workflow

A typical Atlas user experience is:

```text
Receive invitation
        |
        v
Register account
        |
        v
Sign in
        |
        v
Open Portal dashboard
        |
        +--> Discover/Search Media
        |        |
        |        +--> Available --> Open supported playback
        |        |
        |        `--> Requestable --> Submit Request
        |
        +--> Your requests --> Review status / availability
        |
        +--> Favorites --> Add / remove personal Favorites
        |
        `--> Sports --> Review supported events / recordings
        |
        v
Sign out
```

At every step, explicit unavailable or reconciliation states take precedence
over assumptions.

---

## 27. User-Safe Decision Rules

When you are unsure what to do, use these rules:

1. If Atlas shows a normal retry button for a read failure, retry through Atlas.
2. If Atlas says something is already requested, review the existing request.
3. If Atlas says to check requests, check request state before trying again.
4. If Atlas says not to retry, do not retry.
5. If Atlas reports maintenance, wait for the maintenance window to close.
6. If an error persists, contact the administrator rather than bypassing Atlas.
7. Never assume an unavailable provider means your durable Atlas state was
   deleted.

---

## 28. References

This guide summarizes the supported end-user behavior defined and validated by
the Atlas v1.0 source documentation.

Primary references include:

- `../releases/USER_ACCEPTANCE.md`
- `../releases/V1_RELEASE_PLAN.md`
- `../architecture/PORTAL.md`
- `../architecture/MEDIA_DISCOVERY_REQUESTS.md`
- `../architecture/UNAVAILABLE_PROVIDER_BEHAVIOR.md`
- `../architecture/INTERRUPTED_REQUEST_RECOVERY.md`
- `../architecture/SECURITY.md`
- `../SPORTS.md`
- `../../ROADMAP.md`

Administrator-only production and recovery procedures belong in the
Administrator and specialized operator guides, not in normal end-user
instructions.
