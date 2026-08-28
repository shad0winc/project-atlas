# Identity Mutation Boundary

## Purpose
Atlas separates public identity administration from privileged identity-state
persistence. The public API owns authentication, RBAC, validation, and public
HTTP semantics; a private identity writer owns bounded persistence mutations.

## Runtime Boundary
```text
Portal
  |
  v
Atlas API
  | authentication / RBAC / validation
  | users: read-only
  | canonical invitation reads
  |
  | atlas-identity network + Bearer service token
  v
Identity Writer
  | users: read-write
  | identity/invitations: read-write
  v
Authoritative identity state
```

The writer has no public ingress or host-published port. Portal and Caddy are
not members of the private identity network.

## Storage Authority
User profiles remain rooted at `ATLAS_USERS_DIR`. Invitations are canonical at
`ATLAS_IDENTITY_DIR/invitations`. The API mounts user state read-only; the
writer receives RW mounts only for users and canonical invitations. Favorites,
runtime requests, audit events, and the broader identity tree are not writable
through the writer.

## Mutation Flow
1. Portal calls the public API.
2. API authenticates the caller.
3. API evaluates administrator permission.
4. API validates the request.
5. API delegates the bounded mutation.
6. Writer authenticates the service token.
7. Writer invokes the existing identity domain store.
8. Writer returns the bounded result.
9. API preserves the established public response/error contract.

The writer does not replace public RBAC.

## Writer Surface
- `GET /health`
- `PATCH /internal/v1/users/{identifier}`
- `POST /internal/v1/invitations`
- `POST /internal/v1/invitations/{invite_id}/revoke`

Mutation routes require the dedicated Bearer token. Health remains available
for readiness verification. Writer docs/OpenAPI publication are disabled.

## Runtime Hardening
The writer joins only `atlas-identity`, publishes no host port, uses
`no-new-privileges`, a read-only root filesystem, temporary `/tmp`, bounded
resources, and only required identity configuration. It does not inherit the
public JWT secret. The API requires both writer URL and token and fails closed
when configuration is absent.

## Failure Semantics
Writer HTTP failures become the internal writer-error contract; public admin
routes preserve the writer status and established public response shape.
There is no direct-filesystem fallback.

## Local Administrative Workflows
Trusted local Atlas CLI workflows may continue using filesystem-backed identity
domain services. This boundary limits privilege for the public API runtime.

## Deployment Requirement
Production must provide a strong `ATLAS_IDENTITY_WRITER_TOKEN` through the
established secret-management path. It must never be committed. Deployment
must verify writer health before Administrator acceptance resumes.

## Verification
T42-F02 contracts cover runtime isolation, authentication, canonical storage,
delegation, RBAC ordering, errors, secret hiding, health, and direct-write
regression protection. Certified state: 37 focused tests; 3,495 Core plus 104
subtests; 423 API plus 15 subtests.

See [ADR 0025 — Identity Mutation Boundary](../ADR/0025-identity-mutation-boundary.md).
