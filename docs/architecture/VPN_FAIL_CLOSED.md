# VPN Fail-Closed Verification Architecture

## Purpose

This document defines how Project Atlas verifies that qBittorrent remains
isolated behind Gluetun when the VPN tunnel is healthy, degraded, unavailable,
and restored.

The goal is not merely to confirm that qBittorrent normally uses a VPN. The
v1.0 requirement is stronger: loss of the VPN must remove usable internet
egress rather than expose a fallback path.

## Security Invariant

qBittorrent must have no usable non-VPN internet egress path while its required
VPN tunnel is unavailable.

Atlas treats this as a fail-closed security boundary. Unknown or contradictory
evidence must not be interpreted as proof of isolation.

## Existing Production Boundary

The current Compose design provides four complementary controls:

- qBittorrent uses `network_mode: "service:gluetun"`;
- qBittorrent publishes no ports or independent Compose network of its own;
- Gluetun owns the namespace, has `NET_ADMIN` and `/dev/net/tun`, and is
  configured with `FIREWALL=on`; and
- qBittorrent depends on Gluetun using `condition: service_healthy`.

The qBittorrent Web UI and peer ports are published by Gluetun because Gluetun
owns the shared network namespace.

These controls are necessary. They are not, individually or collectively,
substitutes for observing the failure path.

## Separation of Responsibilities

### Namespace isolation

Docker Compose owns the structural relationship. qBittorrent must not receive
an independent network namespace or alternate network attachment that could
bypass Gluetun.

### Tunnel and firewall enforcement

Gluetun owns tunnel establishment, routing, DNS/network policy, and the
firewall inside the shared namespace. Atlas must not weaken Gluetun firewall
rules to perform verification.

### Startup readiness

Startup Policy verifies that a namespace-sharing dependent waits for Gluetun
health. This prevents normal startup from accepting process existence as VPN
readiness.

Startup Policy does not prove what happens after a healthy tunnel later fails.

### VPN verification

VPN verification owns evidence that healthy qBittorrent egress is routed
through the shared VPN namespace and, when explicitly approved, that egress is
unavailable while the VPN path is absent.

## Evidence Model

M-023.21 uses three evidence classes.

### 1. Static configuration evidence

Static checks establish the intended contract:

- qBittorrent network mode targets Gluetun;
- qBittorrent has no independent Compose network attachment;
- qBittorrent ports are published on Gluetun;
- Gluetun firewall is enabled;
- Gluetun has the required network capability and tunnel device; and
- qBittorrent requires Gluetun health before startup.

A configuration regression in any required control fails verification.

### 2. Read-only runtime evidence

Production inspection should establish, without mutating networking:

- both containers are in their expected runtime state;
- qBittorrent is using Gluetun's runtime network namespace;
- the VPN tunnel interface is present while Gluetun is healthy;
- routes and firewall state are consistent with Gluetun ownership;
- qBittorrent has no independent Docker network attachment; and
- healthy-path egress from the shared namespace succeeds.

Runtime inspection must redact credentials and avoid logging sensitive
environment values.

### 3. Controlled failure evidence

The strongest proof requires a reversible VPN interruption performed only with
explicit operator approval.

During the interruption:

- the VPN tunnel is expected to become unavailable;
- an outbound connectivity probe from the qBittorrent namespace must fail;
- success of a non-VPN outbound probe is a critical validation failure; and
- no firewall or route may be added to manufacture an alternate path.

After restoration:

- Gluetun must return to healthy;
- the tunnel must be present again;
- outbound connectivity must recover; and
- the recovered egress must still use the VPN path.

## Healthy-Path Egress Is Not Fail-Closed Proof

The existing `atlas verify` VPN check executes an external-address probe from
the qBittorrent container. That is useful evidence that egress works through
the shared namespace when the VPN is available.

It does not demonstrate that egress fails when the tunnel disappears.
M-023.21 therefore preserves the healthy-path check while adding independent
failure-path evidence rather than redefining a successful network request as
proof of the kill switch.

## Failure Semantics

The following conditions fail VPN fail-closed verification:

- qBittorrent gains an independent network attachment;
- qBittorrent no longer targets Gluetun's namespace;
- Gluetun's firewall is explicitly disabled;
- startup readiness is weakened below Gluetun health;
- runtime namespace ownership contradicts Compose intent;
- fail-closed evidence is unavailable but the result is reported as proven;
  or
- internet egress remains usable through a non-VPN path during an approved
  VPN-loss test.

Unavailable or incomplete runtime evidence is `unknown`, not `safe`.

## Test Strategy

Focused automated tests should lock down the static contract and verifier
failure behavior without requiring a real VPN.

Production validation is layered:

1. validate repository and working-tree guards;
2. inspect normalized Compose configuration;
3. inspect runtime namespace and Gluetun health;
4. inspect tunnel, route, and firewall evidence read-only;
5. capture healthy-path qBittorrent egress;
6. run release-quality checks; and
7. only if needed and separately approved, run the controlled VPN-loss test.

The read-only phase and controlled phase must produce separate checkpoints so
the project never implies that a mutation occurred when only observation was
performed.

## Operational Safety

VPN-loss validation can temporarily interrupt downloads and tracker traffic.
It must therefore be short, reversible, and explicit.

The validation procedure must restore service even when an assertion fails.
Repository state and Compose configuration must remain unchanged throughout
the controlled test.

## Scope Boundaries

M-023.21 does not:

- replace Gluetun;
- change Windscribe configuration;
- add a second VPN implementation;
- grant qBittorrent an alternate network path;
- expose qBittorrent directly to the public internet;
- disable the Gluetun firewall for testing; or
- introduce automatic VPN interruption.

## Related Documents

- [ADR-0019: VPN Fail-Closed Enforcement Boundaries](../ADR/0019-vpn-fail-closed-enforcement-boundaries.md)
- [ADR-0005: Docker Networking](../ADR/0005-docker-networking.md)
- [Startup Policy](STARTUP_POLICY.md)
- [Service Lifecycle](SERVICE_LIFECYCLE.md)
