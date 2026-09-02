# ADR 0025 — Identity Mutation Boundary

## Status
Accepted for the v1.0.0-rc.1 remediation branch.

## Context
The Atlas public API requires read access to identity state while administrator
workflows require bounded user and invitation mutations. Making the public API
identity mount writable would expand the privilege of an Internet-facing
service. T42-F02 therefore introduces a dedicated mutation authority.

## Decision
Atlas uses a private `identity-writer` service for administrator identity
persistence. The public API retains authentication, authorization, validation,
public response semantics, read-only user-profile access, and canonical
invitation reads. Validated user updates, invitation creation, and invitation
revocation are delegated to the writer using a required dedicated service
token.

The writer:
- joins only `atlas-identity`;
- has no public ingress or host-published port;
- receives RW access only to users and canonical invitations;
- does not receive broad identity-tree RW access or the public JWT secret;
- exposes health plus bounded internal mutation routes;
- requires Bearer authentication for mutations;
- uses a read-only root filesystem and `no-new-privileges`.

Canonical invitations are stored under `ATLAS_IDENTITY_DIR/invitations`, not
beneath `ATLAS_USERS_DIR`. Trusted local administrative CLI workflows remain
outside this public-runtime boundary.

## Consequences
The public API cannot silently fall back to direct filesystem mutation.
Production must provide `ATLAS_IDENTITY_WRITER_TOKEN`; configuration fails
closed rather than using an insecure default. The writer is a security-sensitive
runtime component and must participate in deployment readiness and recovery
reviews. Public RBAC remains an API responsibility.

## Verification
Contracts cover least-privilege networking/mounts, canonical paths, required
service authentication, invalid/missing tokens, absence of public writer
routes, API RO state, delegation, RBAC-before-writer resolution, public
response/error preservation, secret hiding, health, and direct-write
regression protection.

Certified before documentation reconciliation:
- focused T42-F02: 37 passed;
- Core: 3,495 passed plus 104 subtests;
- API: 423 passed plus 15 subtests;
- Python compile, Compose validation, and `git diff --check`: PASS.

## Alternatives Rejected
- Public API users RW: unnecessarily expands privilege.
- Individual writable file mounts: incompatible with directory persistence and
  atomic replacement semantics.
- Broad writer identity RW: exceeds required authority.
- Unauthenticated private-network mutations: network placement is not service
  authentication.

## Related Documentation
- [Identity Mutation Boundary](../architecture/IDENTITY_MUTATION_BOUNDARY.md)
- [Security Architecture](../architecture/SECURITY.md)
- [ADR 0024 — Security Trust Boundaries](0024-security-trust-boundaries.md)
- [Backup and Recovery](../architecture/BACKUP_RECOVERY.md)

## T42S runtime-permission clarification

ADR-0025's bounded mutation authority includes the host filesystem authority
needed to make the two approved writer mounts actually writable. Compose
`rw` flags alone are insufficient.

Deployment must establish and verify the following directory-root contract
before ingress services are applied:

- users: UID `0`, GID `20000`, mode `2770`;
- canonical invitations: UID `0`, GID `20001`, mode `2770`.

This is a deployment prerequisite, not an expansion of the writer's mutation
surface. Provisioning is limited to those directory roots, is non-recursive,
and preserves existing child ownership and modes. Failure to establish the
contract aborts ingress deployment before Compose apply.
