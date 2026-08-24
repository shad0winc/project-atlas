# Release Promotion and Production Source Gate

This document owns the repository promotion and production-source gate. It does
not own the complete production upgrade, rollback, or restore procedure.

## Canonical v1 operator guides

Project Atlas v1 operational procedures are owned by the guides under
`docs/guides/`. Use the guide that matches the transaction you are performing:

| Guide | Canonical responsibility |
|---|---|
| `docs/guides/ADMINISTRATOR_GUIDE.md` | Administrator workflows and operational navigation |
| `docs/guides/USER_GUIDE.md` | End-user workflows and user-safe failure behavior |
| `docs/guides/INSTALLATION_GUIDE.md` | New installation and initial production verification |
| `docs/guides/UPGRADE_GUIDE.md` | Production upgrade transaction |
| `docs/guides/ROLLBACK_GUIDE.md` | Deployment rollback transaction |
| `docs/guides/BACKUP_RESTORE_GUIDE.md` | Atlas backup and state-restore transaction |
| `docs/guides/TROUBLESHOOTING_GUIDE.md` | Diagnosis, incident handling, and failure recovery |

Older documents may retain architecture, implementation history, command contracts,
or service-specific reference material, but they do not override these procedure
owners. When instructions conflict, stop and follow the applicable canonical guide.

Project Atlas production deployment has two complementary safety boundaries:

1. repository-hosting rules prevent untested source from being promoted into
   the stable production branch; and
2. the production `atlas update` command verifies that the local source is a
   clean `main` checkout exactly matching `origin/main` before runtime mutation.

Neither boundary replaces the other.

## Branch Flow

The normal release flow is:

```text
feature/fix/docs -> release/<version> -> main -> certified annotated tag
```

Focused branches are development surfaces and are never direct production
deployment sources. A permanent `develop` branch is not required.

## Atlas Release Gate

`.github/workflows/release-gate.yml` runs for pull requests and pushes targeting
`main` or `release/**` and may also be dispatched manually.

The workflow independently validates:

- the complete core Python regression;
- the API package and API regression;
- the Sports integration suite;
- Portal lint, type-check, tests, and production build; and
- shell/deployment safety contracts.

The final job is named `release-gate`. It succeeds only when every required
validation surface succeeds. Branch protection should require this stable final
check rather than coupling repository policy to every individual job name.

## Required Repository-Hosting Rules

Repository configuration is an external production control and is not proven
merely because a workflow file exists.

Repository hosting was inspected during M-023.24 and an active production
promotion ruleset was configured for `main` and `release/**`. The enforced
boundary requires:

- changes to be merged through pull requests;
- the aggregate `release-gate` status check to pass;
- protected branches to be up to date before merge;
- force pushes to be blocked;
- branch deletion to be blocked; and
- an empty default bypass list.

The required check identity was selected only after the workflow had produced
the real `Atlas Release Gate / release-gate` check. Feature source was promoted
through `release/v1.0.0` and then through a second protected pull request into
`main`; pull-request and push runs of the release gate passed on the certified
path.

Release-scoped fixes discovered before final certification continue through
the same model: a focused `fix/*` branch is reviewed into the active
`release/<version>` certification surface, the aggregate gate must pass, and
the resulting release state is promoted to `main` through another protected
pull request. A passing development branch is never itself a production
deployment source.

## Production Deployment Source

Passing CI does not itself deploy production.

After an approved release is promoted to `main`, production deployment must
follow `docs/guides/UPGRADE_GUIDE.md`. The `atlas update` source gate independently
requires:

- branch `main`;
- a clean working tree;
- local `HEAD` exactly equal to `origin/main`;
- a verified production deployment baseline;
- an explicit migration declaration; and
- the remaining deployment transaction gates.

## Production Recovery Source

Protected promotion is also part of the live-restore authorization boundary.
The complete state-restore transaction is owned by
`docs/guides/BACKUP_RESTORE_GUIDE.md`; deployment rollback is owned by
`docs/guides/ROLLBACK_GUIDE.md`.
`atlas restore apply` refuses production mutation unless the checkout is clean
`main` exactly equal to `origin/main`; `--confirm-live` cannot override an
uncertified feature or release checkout. M-023.25 explicitly exercised that
rejection on `feature/backup-recovery` and proved no lock, maintenance, writer,
backup-retention, deployment-baseline, or repository mutation began.

After promotion through the required feature -> release -> main path, the same
certified tree completed the controlled live restore from production `main`.
Live restore additionally requires a verified deployment baseline, the shared
deployment/update lock, staged recovery validation, a fresh pre-restore
recovery point, maintenance isolation, writer quiescence, and explicit
`--confirm-live`.

## Migration Boundary

The current automatic transaction accepts only an explicit:

```text
--migration none
```

This is intentionally conservative. A schema or configuration migration must
have release-specific compatibility, backup, validation, and recovery evidence
before production automation may authorize it. Missing migration evidence
blocks deployment.

## Existing v1.0.0 Tag

The historical `v1.0.0` tag remains a separate release blocker. This workflow
does not reinterpret, move, delete, or accept that tag as current certification
evidence. Tag reconciliation remains an explicit project-owner release action.
