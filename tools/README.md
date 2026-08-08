# Atlas Engineering Tools

The `tools/` tree contains repository-managed engineering utilities that support
development, maintenance, migrations, and releases without mixing temporary
artifacts into the repository root.

## Directories

- `apply/` — active, reviewable implementation helpers for focused engineering
  sprints.
- `maintenance/` — safe repository or platform maintenance utilities.
- `migrations/` — explicit, versioned data or configuration migrations.
- `release/` — release validation, packaging, and tagging helpers.
- `archive/` — documentation for retired tooling retained for historical value.

## Rules

1. Product runtime code does not depend on `tools/`.
2. Temporary exports, review bundles, and one-off generated scripts do not belong
   in the repository root.
3. Active tools must be documented, shell-checked, and safe by default.
4. Destructive operations must require explicit targets and validation.
5. Completed one-off tooling should be removed or archived outside the Git
   working tree under `/mnt/storage/backups/atlas/dev-artifacts/`.
6. Reusable tooling may remain tracked when it has an ongoing engineering role.
