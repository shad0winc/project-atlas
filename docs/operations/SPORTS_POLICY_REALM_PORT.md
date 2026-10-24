# Sports credential realm and policy source port

This change ports PR #219's source requirements onto the current release tree.
It does not deploy the Sports writer, edit source registries, migrate accounts or
channel history, enable Dispatcharr verified mode, alter live sessions, or reopen
maintenance. PR #220 remains a separate backend integration proposal.

New provider accounts explicitly supply a credential realm through Portal,
public administration API and the private writer. Legacy source metadata remains
readable with no realm and does not gain verified policy authority. Realm
onboarding and managed-channel history require separately reviewed migrations.

The read-only classification and claim endpoints require a dedicated credential
that cannot equal the writer credential. Claims bind current event/source,
channel, account and realm membership; they are not provider capacity observations
and do not independently authorize playback.

The port retains current metadata and pinned single-feed sharing routes. It adds
the missing policy-module COPY to the writer image so its new import is packaged,
and appends the optional realm dataclass field to preserve existing positional
source construction. Tests cover both regressions.

Validation is recorded by the source preparation receipt and protected release
CI. Local focused tests do not replace API/Portal CI or production acceptance.
Existing accepted Sports receipts retain their original scope. Future backend
integration must preserve the current HEAD compatibility fix, per-user session
ownership and release behavior, and must separately reconcile credential capacity
and live/VOD/timeshift migration before strict mode is enabled.
