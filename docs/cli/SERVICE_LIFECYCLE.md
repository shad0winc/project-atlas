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

Shows dependency relationships, reverse relationships, and unresolved
dependencies.

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
