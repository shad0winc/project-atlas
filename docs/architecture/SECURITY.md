# Security Architecture

## Purpose

This document defines the Project Atlas v1.0 security boundaries reviewed
and hardened through M-023.26. It records the observed production baseline,
the resulting source security contracts, intentionally retained capabilities,
deployment-only transitions, and the evidence still required for final v1.0
security certification.

M-023.26 engineering review is complete. Final release security acceptance
remains separate and requires controlled deployment, current vulnerability
evidence, runtime validation, documented residual-risk acceptance where
applicable, and release approval.

## Trust Model

Atlas has four principal trust zones:

1. the public browser and Internet-facing Caddy boundary;
2. the internal Portal/API application boundary;
3. operator-controlled host configuration and recovery state;
4. media/infrastructure services and the Docker control plane.

The browser is untrusted input. Caddy is the only intended public Atlas ingress.
The API authenticates identity and authorizes permissions. Operator state owns
secrets and recovery material. Docker access and direct backend administration
are privileged infrastructure capabilities rather than ordinary application
features.

## Observed M-023.26 Baseline

The initial review was performed from certified main `fc46cde0` and production
baseline `baseline-20260808T043132Z-2166158`.

Observed controls:

- `atlas-caddy` publishes TCP 80/443 and UDP 443 for Atlas public ingress;
- `atlas-api` and `atlas-portal` use internal Docker exposure rather than host
  port publication;
- the API image runs as the dedicated `atlas` user;
- ingress containers use `no-new-privileges`;
- Caddy uses a read-only root filesystem with bounded writable mounts;
- HSTS, MIME sniffing protection, frame denial, referrer policy, permissions
  policy, COOP, and server-header removal are configured;
- the root `.env` was mode `0600` and owned by root;
- JWT validation pins HS256 and validates issuer, audience, token type, JTI,
  subject, timestamps, and required claims;
- authorization uses explicit permission dependencies and denies absent grants;
- invitation durable state stores token hashes rather than plaintext tokens;
- Portal access and refresh credentials remain in browser process memory.

The initial discovery identified the following gaps for M-023.26
resolution:

- `ATLAS_JWT_SECRET` was absent from the running `atlas-api` environment;
- `/api/docs` and `/api/openapi.json` returned HTTP 200 publicly;
- Caddy JSON access logging had no explicit sensitive-URI redaction contract;
- no Content Security Policy header was configured at the public Portal
  boundary;
- multiple media/administration services published host ports on all host
  interfaces;
- Homepage and Dozzle mounted `/var/run/docker.sock`, even though the mount was
  marked read-only;
- module `.env` files observed during discovery used mode `0644` and therefore
  require secret-content/permission review without disclosing their values;
- refresh tokens had signed expiration semantics but no reviewed replay or
  revocation boundary;
- no reviewed authentication rate-limit boundary had been established.

## Authentication

Atlas API settings require a signing secret of at least 32 characters. Default
issuer and audience are `project-atlas` and `atlas-portal`. Access tokens are
short lived; refresh tokens have a longer bounded lifetime.

For production, valid settings are a readiness requirement, not merely a
dependency that may fail after the container has already become healthy.
Compose/runtime wiring must explicitly provide required settings without
embedding their values in tracked source.

Authentication errors exposed to a remote client must remain generic enough to
avoid turning login into an account-discovery interface.

## Authorization

Authentication and authorization remain separate. Route-level permission
dependencies are the authoritative HTTP boundary. Subject inactivity, missing
identity, invalid roles, missing grants, and explicit denials fail closed.

M-023.26 established deterministic authorization and route-boundary
regression coverage so accidental unguarded application routes fail review
rather than silently expanding the public API surface.

## Session and Browser Boundary

The Portal currently keeps bearer credentials only in process memory. This is
the desired v1.0 persistence model: browser refresh or terminal authentication
failure clears the local authenticated session.

Because bearer credentials are available to page JavaScript, the public
response boundary needs a tested CSP compatible with the Portal build. Header
hardening must be verified through Caddy after deployment, not only by source
inspection.

## Invitation Boundary

Invitation tokens authorize creation of a user identity and are therefore
credentials. Atlas hashes them at rest, uses constant-time digest comparison,
and treats delivery, registration routing, proxy logging, event payloads, and
failure handling as credential-sensitive boundaries. Plaintext invitation
tokens must not become durable operational data.

## Reverse Proxy and API Exposure

Caddy owns TLS and public routing for `atlas.shadowinc.co`. Portal and API
containers must not publish host ports. Public production API documentation is
not required for the friends-and-family v1.0 deployment and should be disabled
at the external runtime boundary while preserving in-process OpenAPI generation
for API contract tests.

Access logging must remain useful for operations without persisting security
credentials. Query strings and other credential-bearing request material need
an explicit redaction or avoidance contract.

## Secret Storage

Tracked source may contain names, placeholders, and validation contracts for
secrets, but never production values. Operator-managed secret state must be
owned by the intended operator and use restrictive filesystem permissions.

Runtime injection follows least consumer privilege: a service receives only
the secrets it actually needs. Validation tooling reports presence and policy,
not values.

## Infrastructure Exposure and Least Privilege

The security review inventories every running container for:

- published host ports and bind addresses;
- container user identity;
- privileged mode;
- Linux capability additions;
- `no-new-privileges`;
- read-only root filesystems where practical;
- sensitive writable mounts;
- Docker-socket access.

Not every administrative service must become Internet accessible through
Atlas. Services retained for trusted-LAN administration must be explicitly
bound/documented as such. Docker-socket consumers receive special scrutiny
because socket access crosses the container/host control boundary.

## Audit Events

Security audit evidence records bounded facts such as action class, time,
subject identity where appropriate, and outcome. Credential material is never
an audit field. Authentication failures, invitation lifecycle, authorization
denials where operationally useful, and high-impact administrative operations
are reviewed as candidate event classes.

Audit design must avoid creating a password/token oracle or flooding durable
state during an online guessing attempt.

## Dependency Vulnerability Review

M-023.26 reviewed the Python and Node dependency surfaces together with
relevant deployed container-image selections. Atlas now protects reviewed
third-party image choices with immutable source contracts where required,
including the maintained Seerr and Maintainerr selections.

Advisory information remains time-sensitive. Final v1.0 security certification
therefore requires current scan evidence and does not treat historical review
or an immutable image selection as proof that future vulnerability findings do
not exist. Any release-blocking finding must be remediated or explicitly
accepted with bounded scope and rationale before publication.

## Validation Strategy

Security changes use the normal Atlas guarded workflow:

1. exact branch, commit, and clean-tree guards;
2. focused regression tests for the changed boundary;
3. syntax/configuration validation;
4. full Core regression;
5. protected feature -> release -> main promotion;
6. controlled production synchronization;
7. read-only or explicitly authorized runtime security probes;
8. proof that the deployment baseline, maintenance state, backup/recovery
   boundary, and repository state remain resolved.

No secret values are printed during validation.

## M-023.26 Result

M-023.26 completed the ten Security engineering-review work packages through
bounded source changes, deterministic inspection, focused security contracts,
full regression testing, and controlled runtime evidence where appropriate.

The resulting v1.0 source boundary includes:

- fail-closed authentication configuration and bounded abuse controls;
- explicit deny-by-default authorization and route-boundary coverage;
- reviewed ephemeral browser-session and refresh-token behavior;
- invitation-secret handling and proxy/logging protections;
- hardened browser, reverse-proxy, and API exposure contracts;
- restrictive secret-file and secret-consumer boundaries;
- credential-safe security audit-event contracts;
- reviewed dependency and immutable third-party image selections;
- first-party non-root runtime identities and reduced module mount capability;
- explicit network trust boundaries for identity and indexer-proxy access.

Some capabilities intentionally remain outside source-only closure. Homepage
and Dozzle retain read-only Docker-socket access for operational functionality;
the Docker API is still a privileged host-control boundary and this capability
must remain explicitly documented and accepted for v1.0 if retained.

The hardened Notifications and Sports images are source-validated as non-root,
but production ownership migration and container recreation are deployment
operations. They must occur only through the backed-up, maintenance-controlled
deployment path after filesystem ownership and Runtime Bus access preconditions
are satisfied.

Accordingly, completion of the Security roadmap engineering review does not
certify the v1.0 release. Final Security Acceptance remains governed by the
release checklist and requires current vulnerability evidence, controlled
runtime validation, accepted residual limitations, and explicit security
approval.

## Related Decisions

- [ADR-0024: Security Trust Boundaries](../ADR/0024-security-trust-boundaries.md)
- [ADR-0023: Backup and Restore Recovery Boundaries](../ADR/0023-backup-restore-recovery-boundaries.md)
- [Production Deployment Safety](DEPLOYMENT_SAFETY.md)
- [Backup and Recovery](BACKUP_RECOVERY.md)
