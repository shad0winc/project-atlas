# ADR-0019: VPN Fail-Closed Enforcement Boundaries

## Status

Accepted

## Context

Project Atlas routes qBittorrent through Gluetun. The production Compose
configuration gives qBittorrent Gluetun's network namespace, publishes the
qBittorrent ports on Gluetun, enables Gluetun's firewall, and delays
qBittorrent startup until Gluetun reports healthy.

Those controls establish a strong topology and readiness boundary, but a
healthy-path egress check is not sufficient evidence that traffic is blocked
when the VPN tunnel becomes unavailable.

Atlas v1.0 requires explicit verification of the failure path. A transient VPN
failure must never create a non-VPN fallback path for qBittorrent traffic.

## Decision

Atlas defines VPN fail-closed behavior as a security invariant:

> qBittorrent must have no usable non-VPN internet egress path while its
> required VPN tunnel is unavailable.

The invariant is enforced and verified through independent layers:

1. qBittorrent shares Gluetun's network namespace and is not attached to an
   independent Compose network.
2. Gluetun owns the namespace's network interfaces, routes, and firewall
   policy and runs with its firewall enabled.
3. qBittorrent startup depends on Gluetun health, not process existence alone.
4. Atlas verification must treat unavailable qBittorrent egress as the
   expected result during an explicitly controlled VPN-loss test.
5. Recovery is not complete until Gluetun is healthy again and qBittorrent
   egress is observed through the restored VPN path.

## Evidence Boundaries

No single observation proves the invariant.

Static Compose inspection proves intended topology and configuration.
Read-only runtime inspection proves the deployed namespace, route, tunnel,
firewall, health, and egress state while the VPN is available. A controlled
failure test proves that the namespace cannot use a non-VPN fallback route
when the tunnel is unavailable.

Startup health alone does not prove leak prevention. Likewise, observing a VPN
address while the tunnel is healthy does not prove failure-path behavior.

## Controlled Failure Rule

VPN interruption is a production infrastructure mutation and requires
explicit operator approval. Validation must:

- capture the healthy baseline first;
- use the smallest reversible interruption available;
- make no firewall rule that permits fallback traffic;
- expect the egress probe to fail during the interruption;
- stop immediately if non-VPN egress succeeds;
- restore the VPN path;
- wait for Gluetun health;
- prove qBittorrent egress recovery through the VPN; and
- leave the repository and production configuration unchanged.

The test must never intentionally create a leak path in order to prove that a
leak is possible.

## Observability

Verification artifacts should identify the Compose topology, runtime namespace
relationship, Gluetun health, tunnel presence, firewall state, routes, and
egress observations without recording VPN credentials or other secrets.

Expected unavailability during the controlled failure window is a successful
security result, not an operational success state.

## Consequences

### Benefits

- VPN isolation has an explicit, testable security contract.
- Startup readiness and traffic isolation remain separate concerns.
- A future verifier can distinguish healthy egress from fail-closed proof.
- Production validation remains reversible and operator-controlled.

### Costs

- Strongest verification requires a short, explicitly approved VPN
  interruption.
- Read-only inspection cannot by itself close the failure-path proof.
- Validation must account for runtime tooling available inside the shared
  network namespace.

## Compatibility

This decision extends the existing Docker networking and Startup Policy
contracts. It does not replace Gluetun, change VPN providers, add a second
network path, or introduce automatic VPN mutation.

Related records:

- [ADR-0005: Docker Networking](0005-docker-networking.md)
- [ADR-0011: Startup Policy Readiness Contracts](0011-startup-policy-readiness-contracts.md)
- [Startup Policy Architecture](../architecture/STARTUP_POLICY.md)
- [VPN Fail-Closed Verification Architecture](../architecture/VPN_FAIL_CLOSED.md)
