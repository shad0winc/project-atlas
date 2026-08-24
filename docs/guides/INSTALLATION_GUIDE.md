# Project Atlas Installation Guide

**Document Status:** D.3C v1.0 Documentation Candidate
**Applies To:** Project Atlas v1.0 installation
**Audience:** Project Atlas administrators and maintainers
**Canonical Repository Path:** `docs/guides/INSTALLATION_GUIDE.md`

---

## 1. Purpose

This guide defines the supported high-level installation workflow for Project
Atlas v1.0.

Atlas installation is environment-sensitive. The repository, Compose
configuration, storage layout, secrets, provider credentials, host devices,
systemd units, and public-ingress configuration must agree before the
installation is treated as usable.

A successful installer exit or a set of running containers is not sufficient
proof that Atlas is correctly installed. Installation ends with Atlas-owned
verification and health checks.

---

## 2. Supported Deployment Model

The current Atlas v1.0 deployment model generally expects:

- a Linux host or virtualized Linux environment;
- Docker Engine;
- Docker Compose;
- Python 3;
- Git;
- persistent Atlas configuration storage;
- persistent Media storage;
- network access to configured providers.

Portal development additionally requires a supported Node.js release and npm,
but ordinary production installation should use the repository's supported
build/deployment path rather than ad hoc development commands.

The current project has been validated on a single-host Linux deployment. This
guide does not claim Kubernetes, clustered high availability, or complete
multi-host disaster recovery support for v1.0.

---

## 3. Repository Location

The canonical Atlas checkout is:

```text
/opt/project-atlas
```

A typical initial repository setup is:

```bash
cd /opt
git clone <atlas-repository-url> project-atlas
cd project-atlas
```

Before installation, confirm that the intended source is checked out and that
the repository is not unexpectedly dirty:

```bash
git status --short
git branch --show-current
git log -1 --oneline
```

Do not install production from an arbitrary unreviewed development commit.

Production source and release promotion are governed separately by the Atlas
release/deployment documentation.

---

## 4. Configuration File

Create the local runtime configuration from the tracked example:

```bash
cd /opt/project-atlas
cp .env.example .env
```

Edit `.env` for the deployment.

The legacy installation source explicitly requires `LXC_IP` to be set where
that variable remains part of the current deployment configuration. Do not copy
an old value from another host without verifying the current repository and
network topology.

Never commit `.env`.

Production secret-bearing configuration must remain external runtime state and
must use restrictive filesystem permissions. The certified production
security boundary uses an operator-only root project `.env`.

After editing the file, use an appropriate restrictive mode, for example:

```bash
chmod 0600 /opt/project-atlas/.env
```

Do not print secret values into support logs, documentation, commit messages, or
diagnostic evidence.

---

## 5. Authentication Configuration

Authentication configuration is a startup requirement for Atlas services that
issue or validate Atlas authentication tokens.

A production installation must provide a valid Atlas JWT signing secret through
the supported runtime configuration.

Missing or invalid authentication configuration must fail closed. A container
appearing healthy while authentication is unusable is not an acceptable v1.0
installation state.

The JWT signing secret:

- is operator-managed;
- must not be committed to Git;
- must not be copied into documentation;
- must not be emitted in diagnostics;
- must not be written to access or audit logs.

Verify secret presence and policy compliance without exposing the secret value.

---

## 6. Storage Prerequisites

Atlas requires persistent storage for configuration, runtime state, backups, and
Media.

The exact host mounts are deployment-specific, but the current Atlas topology
uses persistent storage beneath `/mnt/storage`.

Before installation, verify that required storage is:

- mounted;
- writable by the intended runtime identities;
- large enough for the current Media and backup plan;
- persistent across container recreation;
- owned and permissioned for non-root services that must write to it.

Do not assume that a successful Compose definition proves filesystem ownership.

Non-root runtime ownership is an installation prerequisite. A service can be
correctly defined in source yet fail at runtime if its declared writable paths
do not match its effective container identity.

---

## 7. Media and Download Paths

The historical service-wiring documentation establishes these core in-container
paths:

```text
/downloads/complete
/downloads/incomplete

/media/Movies
/media/TV
```

The current Atlas deployment also supports separate anime service/library
surfaces and Sports storage. Current Compose and architecture are authoritative
for the complete v1.0 path set.

Do not blindly reproduce a legacy two-library configuration if the current
repository defines additional supported roots.

For every enabled service, verify:

1. the host path exists;
2. the container mount resolves to the intended in-container path;
3. the runtime user can perform the required read/write operations;
4. all related applications use the same path model where hardlinks or import
   workflows depend on shared storage identity.

---

## 8. qBittorrent Wiring

The historical Atlas service-wiring contract uses:

```text
Default save path: /downloads/complete
Incomplete path:   /downloads/incomplete
```

and category-specific download paths for Media automation.

Current category names and paths must be verified against the current Compose
and Media automation configuration before production use, especially where
standard Media and anime services use separate categories.

Do not route qBittorrent around the configured VPN safety boundary.

VPN-dependent traffic must remain fail closed when VPN safety cannot be
established.

---

## 9. Sonarr and Radarr Wiring

The historical standard-Media service wiring uses:

```text
Sonarr root: /media/TV
Radarr root: /media/Movies
```

with qBittorrent reached through its Docker service identity.

Where hardlinks are part of the Media workflow, the download and library mounts
must preserve compatible filesystem identity.

Current Atlas also contains separate anime Sonarr/Radarr surfaces. Verify the
current repository-owned service names, roots, categories, and server-side
routing rather than inferring them from the older standard-TV/movie examples.

The browser Portal does not own downstream server IDs or provider routing.

---

## 10. Prowlarr Wiring

Prowlarr should communicate with Media automation services over the internal
Docker network using repository-supported service identities.

Historical examples include:

```text
http://prowlarr:9696
http://sonarr:8989
http://radarr:7878
```

Treat these as topology examples that must match the current Compose service
names.

Verify every configured Prowlarr application from its own test action and then
verify Atlas/Media operation end to end.

---

## 11. Jellyfin Wiring and Hardware Acceleration

Historical Atlas wiring uses Jellyfin libraries rooted at:

```text
/media/Movies
/media/TV
```

The current deployment may include additional Media libraries such as anime and
Sports. Use the repository and current library plan as authority.

Where Intel Quick Sync / VAAPI is used, the historical device contract includes:

```text
/dev/dri/renderD128
```

Before enabling hardware acceleration, verify the device exists on the host and
is correctly exposed to the container.

A configured device path that is absent or inaccessible is not a successful
hardware-acceleration installation.

---

## 12. Media Request Provider Wiring

Atlas browser clients call the Atlas API; they must not connect directly to the
Media request provider or receive provider credentials.

Current v1.0 production uses the repository-approved request/discovery provider
boundary and server-owned routing.

Provider credentials and provider-specific server configuration remain
server-side.

Do not expose provider API keys to the Portal.

Historical internal-URL examples are useful for understanding Docker service
discovery, but current service identities and request-provider configuration are
authoritative.

---

## 13. Public Ingress

Caddy is the sole intended public Atlas ingress.

The Portal and API backends should remain internal to the ingress Docker
network rather than being treated as ordinary Internet-facing services.

The production security boundary requires:

- intentional public exposure through Caddy;
- protected or disabled production API documentation/schema endpoints;
- browser security headers;
- bounded access logging that does not retain sensitive credentials;
- least-privilege container configuration.

Do not expose backend administration ports publicly merely because doing so is
convenient during installation.

---

## 14. Docker and Least Privilege

Infrastructure configuration is part of the Atlas security boundary.

Treat each of the following as a privileged capability:

- host port publication;
- Linux capabilities;
- Docker API/socket access;
- writable mounts;
- container user identity;
- privilege flags.

Each retained capability needs an operational reason.

A read-only Docker socket mount is not automatically safe. Do not introduce new
Docker-control access as an installation shortcut.

---

## 15. Run the Repository Installer

After repository, configuration, storage, and runtime prerequisites are ready,
run the repository-owned installer:

```bash
cd /opt/project-atlas
./scripts/install.sh
```

The installer is the supported repository entry point identified by the
existing installation documentation.

Do not treat this command as proof of final installation success. Continue
through runtime, scheduler, security, and Atlas verification below.

If the installer fails, stop and diagnose the failure before manually
recreating only part of the installation.

---

## 16. Initial Container Review

After installation, inspect the running container state:

```bash
docker ps
```

The historical installation guide stops here, but v1.0 certification requires
more.

Review for:

- expected containers present;
- no unexpected restart loops;
- required health checks passing;
- no unexpected host-port exposure;
- intended non-root runtime identities;
- required storage mounts present.

A running container with broken authentication, provider wiring, storage
ownership, or scheduler dispatch is not a successful Atlas installation.

---

## 17. Atlas CLI Availability

Verify the public Atlas CLI is available:

```bash
atlas help
atlas version
```

If `atlas` is not found, inspect the repository installer outcome and the
supported CLI installation/wrapper path rather than creating an undocumented
alternate entry point.

Use `atlas help` as the authoritative installed command index.

---

## 18. Scheduler Registration

Atlas uses one shared `TaskScheduler`.

Register or reconcile core and enabled-module jobs through the canonical sync
operation:

```bash
atlas scheduler sync
```

An unqualified sync registers core jobs and enabled module jobs.

Targeted module synchronization does not substitute for the unqualified core
synchronization.

Repeated synchronization is intended to be idempotent while preserving
runtime counters and history.

---

## 19. Production Scheduler Dispatcher

Registered tasks do not run autonomously merely because their definitions exist.

Production uses the repository-owned systemd dispatcher:

```text
atlas-scheduler.timer
        |
        | one-minute dispatch opportunity
        v
atlas-scheduler.service
        |
        v
/bin/atlas scheduler run
```

The tracked unit files are:

```text
systemd/atlas-scheduler.service
systemd/atlas-scheduler.timer
```

The timer only provides recurring opportunities for Atlas to evaluate due work.
`TaskScheduler` remains the sole authority for each task's actual cadence,
locking, execution, counters, and history.

Repository tracking alone does **not** install or enable these units.

Host installation must explicitly perform the repository-approved systemd
deployment steps, including:

- install/copy the tracked units to the host's systemd unit location;
- `systemctl daemon-reload`;
- enable the timer;
- start the timer when the current controlled deployment state permits it;
- verify recurring dispatch.

Do not implement a second scheduler daemon or encode task-specific intervals in
systemd.

### 19.1 Release-certification note

A prior v1.0 sustained-use certification intentionally stopped the timer while
leaving it enabled after the certification window closed.

Therefore, before changing the live timer state on an already-existing
production host, verify whether a current release/maintenance procedure owns
that state.

For a new installation, the dispatcher must ultimately be installed and
verified as part of making recurring Atlas Scheduler work operational.

---

## 20. Sports Module Prerequisites

Sports is an optional Atlas module.

When enabled, its runtime uses persistent storage including:

```text
/mnt/storage/media/Sports
/mnt/storage/configs/sportyfin
```

with subdirectories for input, output, logs, recordings, and state.

The Sports module also uses the shared Atlas scheduler runtime.

Before expecting the controller to become healthy, verify its effective
non-root runtime identity can write all declared writable Sports runtime
surfaces.

Do not solve a Sports ownership failure by making the container privileged.

---

## 21. Secrets and File Permissions

After installation, audit secret-bearing configuration.

At minimum:

- root project `.env` must remain outside Git;
- production secret files should be owner-only or otherwise least-readable for
  the service contract;
- module `.env` files must not be left world-readable;
- diagnostics must not reveal secret values;
- invitation tokens, API keys, webhook URLs, JWT secrets, passwords, access
  tokens, and refresh tokens must not appear in logs or evidence.

Use numeric ownership and explicit modes where required by container runtime
contracts.

---

## 22. Verify Atlas

Run Atlas-owned verification:

```bash
atlas verify
atlas doctor
atlas status
```

These commands are part of the documented post-install validation surface.

Do not close installation solely because `docker ps` looks healthy.

If any required Atlas verification fails, installation remains incomplete.

---

## 23. Validate Authentication

Perform a safe authentication validation without exposing credentials.

Confirm that:

- the API starts with valid authentication configuration;
- the Portal can reach the intended public Atlas ingress;
- a valid Atlas user can sign in;
- protected routes reject unauthenticated access;
- authorization remains permission based;
- sign-out or terminal authentication failure removes access to protected
  content.

Do not validate authentication by printing or copying the JWT signing secret.

---

## 24. Validate Public Ingress

Verify that the public Atlas entry point resolves through Caddy and that normal
Portal/API traffic behaves as expected.

Where repository verification tooling applies, use the current ingress
verification script and contracts.

Confirm:

- Caddy is healthy;
- Portal and API backends are reachable through the intended internal topology;
- normal public Portal traffic works;
- normal public API health behavior works;
- protected API documentation remains protected/disabled in production;
- backend services have not been unintentionally exposed directly.

Maintenance-mode validation belongs to controlled maintenance/deployment
testing rather than casual first-install experimentation unless explicitly
required by the installation acceptance procedure.

---

## 25. Validate Providers

Installation is incomplete if configured providers cannot satisfy the supported
Atlas contracts.

Validate applicable providers without destructive mutation:

- Jellyfin connectivity and library visibility;
- Media request/discovery provider health;
- Sonarr/Radarr application connectivity;
- Prowlarr application connectivity;
- qBittorrent connectivity through the intended network/VPN boundary;
- Sports provider health when the module is enabled.

Provider failure must be observable as failure, not misreported as successful
empty data.

---

## 26. Validate Storage and Permissions

Verify all required storage roots are mounted and writable by the service
identities that own them.

Check:

- Atlas configuration/state;
- Atlas backup destination;
- Media libraries;
- download roots;
- request state;
- Scheduler runtime;
- Operations state;
- Sports state when enabled;
- security/audit journals where applicable.

Do not use broad world-writable permissions as a substitute for understanding
ownership.

---

## 27. Validate Backup Creation

After Atlas passes initial health checks, create and validate an initial Atlas
backup:

```bash
atlas backup --notes "post-install validation"
```

Review the command result and confirm the canonical backup is published.

Atlas backup publication is transactional: partial archives are not equivalent
to successful canonical recovery archives.

The Backup/Restore Guide owns the full recovery contract.

A local backup on the same host/storage failure domain does not provide
independent disaster-recovery protection.

---

## 28. Validate Operations and Scheduler

Review the Operations and Scheduler surfaces:

```bash
atlas operations report
atlas operations latest
atlas scheduler list
atlas scheduler history
```

Where recurring dispatch has been enabled, confirm Scheduler history advances
as expected and inspect any failed `atlas-scheduler.service` invocation as a
real Scheduler execution signal.

Do not mask failed dispatcher exit status with a second scheduler.

---

## 29. Installation Acceptance Checklist

Do not declare the installation complete until the applicable checks pass.

- [ ] Repository is present at `/opt/project-atlas`.
- [ ] Intended source/branch/commit is understood.
- [ ] `.env` exists and is not tracked.
- [ ] Secret-bearing configuration has restrictive permissions.
- [ ] Valid authentication/JWT configuration is supplied.
- [ ] Persistent storage is mounted.
- [ ] Required runtime identities can access declared writable paths.
- [ ] Download and Media paths match the current Compose topology.
- [ ] qBittorrent remains inside the intended VPN safety boundary.
- [ ] Jellyfin and Media providers are reachable.
- [ ] Caddy is the intended public ingress.
- [ ] Backend services are not unintentionally publicly exposed.
- [ ] `./scripts/install.sh` completes successfully.
- [ ] Expected containers are running without unresolved unhealthy state.
- [ ] `atlas help` and `atlas version` work.
- [ ] `atlas scheduler sync` has registered core/enabled-module jobs.
- [ ] Production Scheduler dispatcher is installed and verified where required.
- [ ] `atlas verify` passes.
- [ ] `atlas doctor` passes.
- [ ] `atlas status` is understandable and consistent with runtime state.
- [ ] Authentication and protected-route behavior are validated.
- [ ] Storage and provider checks pass.
- [ ] An initial validated Atlas backup exists.
- [ ] No credentials were exposed during installation.
- [ ] No unresolved critical installation failure remains.

---

## 30. What This Guide Does Not Authorize

This Installation Guide does not authorize:

- deployment of an arbitrary feature branch to production;
- bypassing release/promotion gates;
- disabling security controls to make a service start;
- exposing backend services directly to the Internet;
- bypassing the VPN boundary;
- manually deleting Atlas locks;
- extracting unvalidated backups over live state;
- making runtime directories world-writable as a generic fix;
- creating a second Scheduler;
- treating a successful container start as complete acceptance.

Use the specialized Upgrade, Rollback, Backup/Restore, Troubleshooting, and
Administrator guides for those procedures.

---

## 31. Legacy Documentation Reconciliation

The older `docs/01-install.md` remains historically useful because it identifies
the original five-step installation entry point:

1. place the project at `/opt/project-atlas`;
2. create `.env` from `.env.example`;
3. set deployment-specific configuration such as `LXC_IP`;
4. run `./scripts/install.sh`;
5. inspect Docker.

For v1.0, that sequence is a bootstrap summary, not the complete installation
acceptance contract.

Likewise, `docs/02-service-wiring.md` provides useful original examples for
standard Movies/TV wiring but does not by itself describe every current v1.0
service, anime path, Sports path, security boundary, Scheduler dispatcher, or
post-install acceptance requirement.

The current architecture and repository configuration take precedence when they
differ from legacy examples.

---

## 32. Authoritative References

Primary references:

- `../../README.md`
- `../01-install.md`
- `../02-service-wiring.md`
- `../CONFIGURATION.md`
- `../OPERATIONS.md`
- `ADMINISTRATOR_GUIDE.md`
- `../architecture/SECURITY.md`
- `../architecture/DEPLOYMENT_SAFETY.md`
- `../architecture/STARTUP_POLICY.md`
- `../architecture/SERVICE_LIFECYCLE.md`
- `../architecture/VPN_FAIL_CLOSED.md`
- `../architecture/STORAGE_EXHAUSTION.md`
- `../architecture/UNAVAILABLE_PROVIDER_BEHAVIOR.md`
- `../architecture/BACKUP_RECOVERY.md`
- `../ADR/0024-security-trust-boundaries.md`
- `../operations/RELEASE_PROMOTION.md`
- `../SPORTS.md`
- `../../ROADMAP.md`

When legacy installation examples conflict with newer certified architecture,
security, or production behavior, use the newer certified contract.
