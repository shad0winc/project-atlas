# Atlas settings in Dispatcharr workers

The pinned upstream entrypoint starts migrations, static collection, and uWSGI
through `su -`. Its generated profile does not include the Atlas pilot, ledger,
policy origin/token, or scope key settings. Supplying Docker environment values
alone therefore does not establish worker configuration.

The image installer pins the exact upstream entrypoint and changes only those
three application login launches. It uses `su --login --whitelist-environment=`
with an explicit list of six Atlas variable names. Environment values are never
inserted into shell source or copied into the generated profile. Unset values
remain unset; normal default-off behavior stays available. Existing database
control login calls and shutdown behavior are unchanged. Unexpected source drift
refuses the build; the installer is idempotent only for its exact patch.

Before deployment, rebuild from the accepted commit and verify real login-shell
inheritance and worker startup in a disposable container. Earlier routing tests
that injected environment values do not cover the login boundary. Preserve
the existing writer image proof because writer build inputs do not change.

The bootstrap shutdown helper can fall back to PostgreSQL immediate stop.
A stopped-container backup requires independent inspection of PostgreSQL control
state. A success message or Docker exit alone does not prove a clean cluster.
Startup also invokes a Redis readiness/flush helper: mark the ledger only after
startup is complete and empty state is freshly verified under exclusion.

This source correction performs no rollout, secret provisioning, registry
migration, ledger cutover, maintenance change, invitation, or 1.0 release.
