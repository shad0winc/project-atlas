# ADR-0024: Security Trust Boundaries

Status: Accepted — M-023.26 engineering implementation complete

## Context

Project Atlas v1.0 exposes a browser Portal and HTTP API through Caddy while
also coordinating privileged local infrastructure such as Docker, media
services, recovery state, and operator-managed secrets. Authentication and
authorization controls already exist, but a release security review must prove
that those controls are connected correctly at the production boundary and
that auxiliary services do not silently expand that boundary.

M-023.26 discovery confirmed several strong existing contracts:

- the API validates signed JWT issuer, audience, type, identity, timestamps,
  and algorithm;
- authorization is permission based and defaults to denial;
- Portal access and refresh tokens remain in browser process memory rather
  than persistent browser storage;
- invitation records persist token hashes rather than plaintext invitation
  tokens;
- the Atlas API image runs as a non-root user;
- Portal, API, and Caddy use Docker `no-new-privileges`;
- Caddy is the intended public Atlas ingress and publishes ports 80 and 443;
- the root project `.env` is operator-only mode `0600` in production.

Discovery also identified boundaries requiring hardening or explicit
acceptance. The running API did not receive the required `ATLAS_JWT_SECRET`;
production OpenAPI and Swagger documentation were public; access logging did
not redact sensitive URI material; a Content Security Policy was absent;
multiple backend services published host ports; and Homepage and Dozzle
consumed the Docker socket.

M-023.26 subsequently hardened the source-owned authentication, authorization,
session, invitation, ingress, API exposure, secret, audit, dependency-image,
network, and first-party runtime boundaries. Release acceptance remains a
separate gate because source correctness does not replace current vulnerability
evidence, controlled deployment proof, or explicit documentation of retained
privileged capabilities.

## Decision

Atlas adopts the following v1.0 security trust boundaries.

### 1. Authentication configuration is a startup requirement

Any service capable of issuing or validating Atlas authentication tokens must
receive valid authentication configuration explicitly. Production startup must
fail closed when the JWT signing secret is absent or invalid. A container that
is healthy while authentication configuration is unusable is not an acceptable
v1.0 state.

The signing secret remains operator-managed secret state. It must not be
committed to Git, emitted by diagnostics, copied into documentation, or written
to access/audit logs.

### 2. Authorization remains permission based and deny by default

Authentication establishes identity but never implies authorization. API
operations continue to use explicit permission dependencies. Missing,
inactive, deleted, unknown-role, or insufficiently privileged identities fail
closed.

### 3. Browser credentials remain ephemeral

Atlas does not introduce a persistent browser cookie or local-storage token as
part of M-023.26. Bearer credentials remain process-memory state. The Portal
must clear them on terminal authentication failure.

Because bearer credentials are readable by executing page JavaScript, the
public Portal boundary must also be hardened against unintended script and
content execution. Browser security headers, including an appropriate Content
Security Policy, are part of the release boundary.

### 4. Refresh credentials are replay-sensitive

Issuing a new refresh token is not sufficient rotation if the prior credential
can be replayed until expiration. Atlas therefore uses a bounded
refresh-session/revocation contract so rotation does not silently leave the
prior credential with its full original capability.

### 5. Authentication endpoints resist online guessing

Public login and refresh endpoints require bounded abuse controls. Rate
limiting must fail predictably, must not trust arbitrary client-supplied proxy
headers, and must not expose whether a username exists.

### 6. Invitation tokens are credentials

An invitation token is treated as a one-time secret. Durable storage keeps only
its cryptographic hash. Plaintext tokens may exist only while being delivered
or submitted by the invited user and must not be written to application,
proxy, or audit logs. Public routing must avoid retaining invitation secrets in
request URLs where practical.

### 7. Public API exposure is intentional and minimal

Caddy remains the sole intended Internet-facing Atlas entry point. Portal and
API backends remain internal to the ingress Docker network. Production API
documentation and schema endpoints are disabled or explicitly protected; test
code may continue to generate and inspect the OpenAPI schema in process.

All application routes other than deliberately public health, authentication,
and invitation/registration entry points require an explicit authorization
contract.

### 8. Secrets are external runtime state

Secrets remain outside version control and use least-readable filesystem
permissions. Runtime configuration must pass only the secrets a service
requires. Diagnostics may report presence, ownership, and policy compliance but
never secret values.

### 9. Infrastructure follows least privilege

Host port publication, Linux capabilities, Docker-socket access, writable
mounts, container users, and privilege flags are security capabilities. Each
retained capability needs an operational reason. Atlas will remove unnecessary
capabilities and document capabilities that must remain for v1.0.

Read-only Docker-socket mounts are not considered intrinsically safe; access to
the Docker API remains a privileged host-control boundary and must be reduced
or explicitly accepted.

### 10. Security events are auditable without containing credentials

Security-relevant lifecycle events require bounded audit evidence sufficient
to answer what class of action occurred and whether it succeeded. Audit data
must never contain passwords, bearer tokens, refresh tokens, JWT signing
secrets, API keys, webhook URLs, or plaintext invitation tokens.

### 11. Dependency risk is evaluated against current advisories

Static dependency manifests are not sufficient evidence. Release certification
must scan the current Python, Node, and relevant container dependency surfaces
against current vulnerability data and either remediate findings or record an
explicit, bounded acceptance.

## Release Acceptance

M-023.26 engineering implementation is complete and all ten Security roadmap
reviews are supported by automated tests, deterministic inspection, or
controlled runtime evidence appropriate to the reviewed boundary.

This does not constitute v1.0 Security Acceptance. Before release, current
certification evidence must still prove:

- authentication configuration is present and fail-closed;
- unauthenticated protected API access is rejected;
- permission enforcement remains deny-by-default;
- invitation material does not persist in plaintext durable state or logs;
- browser/session exposure and security headers satisfy the documented policy;
- only accepted public/network surfaces remain exposed;
- secret files and secret injection obey least-readable/least-consumer rules;
- security audit records contain no credential material;
- dependency scans have no unreviewed release-blocking findings;
- retained container privileges have explicit justification, including any
  retained Docker-socket capability;
- the non-root module ownership transition has been completed and validated
  through the controlled deployment path;
- the repository, verified deployment baseline, recovery boundary, and normal
  maintenance state remain intact through validation.

## Consequences

This decision makes security configuration part of runtime correctness rather
than optional deployment convention. Some currently convenient development
surfaces may be disabled in production, and some local service access may need
to become explicitly LAN-bound or proxy-mediated.

The design intentionally avoids adding a second identity system, a second
reverse proxy, or a generalized secret-management platform for v1.0. Existing
Atlas identity, authorization, Caddy, Docker Compose, and operator-managed
configuration remain the implementation foundations.

## Related Documentation

- [Security Architecture](../architecture/SECURITY.md)
- [Backup and Recovery](../architecture/BACKUP_RECOVERY.md)
- [Production Deployment Safety](../architecture/DEPLOYMENT_SAFETY.md)
- [ADR-0023: Backup and Restore Recovery Boundaries](0023-backup-restore-recovery-boundaries.md)
