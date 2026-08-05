# Service Lifecycle CLI

## Purpose

The Service Lifecycle CLI provides read-only operational inspection for
Atlas-managed services. It is a presentation layer over normalized domain
services and providers.

No Service Lifecycle CLI command in Atlas v1.0 pulls images, restarts services,
stops containers, starts containers, recreates containers, or otherwise mutates
Docker.

## Command summary

```text
atlas service list [--json]
atlas service show <identifier> [--json]
atlas service runtime <identifier> [--json]
atlas service health [<identifier>] [--json]
atlas service summary [--json]
atlas service graph [--json]
atlas service doctor [--json]
atlas service updates [--json]
atlas service history [<identifier>] [--json]
atlas service startup-policy [--json]
atlas service recovery observe <identifier> [--json]
atlas service recovery evaluate <identifier> --before <path> [--json]
atlas service help
```

Legacy compatibility remains available through:

```text
atlas services
```

## Inventory

### `atlas service list`

Lists normalized Atlas-managed services.

Human output is intended for operators. JSON output is the canonical
machine-readable inventory contract.

### `atlas service show <identifier>`

Shows normalized identity, image, runtime, and health information for one
managed service.

## Runtime and health

### `atlas service runtime <identifier>`

Shows normalized runtime state for one managed service.

### `atlas service health`

Shows aggregate infrastructure health.

### `atlas service health <identifier>`

Shows normalized health for one managed service.

### `atlas service summary`

Shows concise service, runtime, and health totals.

### `atlas service graph`

Shows the normalized dependency topology for all managed services, including:

- direct dependency relationships;
- reverse dependents;
- root services;
- standalone services;
- unresolved dependency identifiers;
- provider, Compose project, service, and edge totals.

Human output provides an operator-readable relationship tree. JSON output
serializes the canonical `InfrastructureDependencyGraph` contract. The command
is read-only and does not start, stop, restart, or reorder services.

## Diagnostics

### `atlas service doctor`

Runs read-only diagnostics across managed services.

Diagnostics can identify:

- unhealthy services;
- stopped services;
- missing health checks;
- dependency issues;
- restart-loop evidence;
- configuration and observability warnings.

JSON output serializes the canonical `DoctorReport` contract.

## Update Discovery

### `atlas service updates`

Shows read-only service image update metadata.

Local-only discovery classifies:

- `latest` as `mutable-tag`;
- pinned tags as `unknown` until registry comparison exists;
- digest-pinned images as `unknown` until registry comparison exists.

Local metadata alone never produces `update-available`.

JSON output serializes the canonical `UpdateReport` contract.

## Maintenance History

### `atlas service history`

Shows global maintenance history.

### `atlas service history <identifier>`

Shows maintenance history for one managed service.

Until a persistence provider is introduced, valid empty reports are expected.

JSON output serializes the canonical `MaintenanceReport` contract.

## Startup Policy

### `atlas service startup-policy`

Evaluates normalized startup contracts without modifying infrastructure. Human
output reports provider, status, pass state, attention state, severity totals,
findings, recommendations, and evaluation time. JSON output serializes the
canonical `StartupPolicyReport` for scripts and future API, Portal, and guarded
automation consumers.

## Restart Recovery

### `atlas service recovery observe <identifier>`

Captures one immutable `ServiceRecoveryObservation` through the read-only
Service Lifecycle boundary. Human output summarizes runtime, health, restart
count, start time, and observation time. Use `--json` to save the canonical
before contract for a later comparison.

### `atlas service recovery evaluate <identifier> --before <path>`

Loads and revalidates a saved before observation, captures the current after
observation, and renders one deterministic `ServiceRecoveryResult`. Human output
reports status, restart evidence, restart-count delta, start-time evidence,
attention state, reason, warnings, errors, and evaluation time. `--json` emits
the complete normalized result.

A `recovered` result returns exit code `0`. Conservative outcomes such as
`not-observed`, `recovering`, `degraded`, `failed`, and `unknown` return exit
code `1`. The CLI never performs the restart itself.

Example read-only baseline validation:

```bash
atlas service recovery observe jellyfin --json > /tmp/jellyfin-before.json
atlas service recovery evaluate jellyfin --before /tmp/jellyfin-before.json
```

## JSON behavior

All `--json` commands:

- write valid JSON to standard output;
- preserve normalized field names;
- use UTC timestamps;
- avoid human-only formatting;
- are intended for scripts, future APIs, and the Administration Portal.

## Exit behavior

Successful commands return exit code `0`.

Normalized Service Lifecycle errors return exit code `1` and write a concise
message to standard error.

Argument parsing errors use the standard CLI parser behavior.
