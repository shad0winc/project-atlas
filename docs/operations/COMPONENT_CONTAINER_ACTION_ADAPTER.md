# Held component container action adapter

The API, Portal and Caddy surfaces have an inspection-model adapter and bounded
local-daemon Compose recreation. There is no deployment dispatcher or admission
coordinator. Real target inspection models and real-daemon canaries remain pending.

Execution recipes are derived from the accepted target/rollback recipes. Changes
are limited to immutable image IDs, disabling implicit bind-directory creation,
and requiring existing named networks/volumes via external references. Dynamic
hooks, builds, unresolved interpolation, additional services and unreviewed
config/secret resource definitions refuse preparation.

Recreation selects one of api, portal or caddy and uses --no-deps, --no-build,
--pull never, --force-recreate and a bounded health wait. No down, orphan removal,
volume renewal, image build/pull, or unrelated service is invoked. The client is
pinned to the local Unix daemon with a controlled environment and the actual
account home for Docker CLI discovery. The admission coordinator must pin the
CLI/account configuration as well as the prepared inspection profiles. All needed images,
networks, volumes and bind sources must already exist before recreation.

Profiles preserve the full Config, HostConfig and Mounts inspection fields plus
network memberships, configured aliases, static IPAM and driver options. Only the
automatic hostname, configured image reference and four generated Compose metadata
labels are normalized. The immutable image ID is always retained; a generated
Compose image label must match it. Runtime identity binds container ID, PID, start
time and restart count. Health-log churn does not change identity. A container must
be running and healthy before its result is accepted.

The coordinator must obtain and pin actual inspection profiles for both recipes
and verify those recipes against the profiles before production admission. This
stage does not infer target models from source or claim that fixture models are
production evidence. Unknown, missing, duplicate or unhealthy runtime states refuse
recovery actions. A changed unrelated-runtime guard also refuses. Full observations
of the other containers are compared around each replacement.

After interruption an exact healthy target can be confirmed without another
recreation. Uncertain command results keep their journal intent. Rollback reverses
Caddy, Portal and API before stopping the authority, retaining the unit, confirming
manager removal, and retaining the source. Any remaining generation bind blocks
source retention.

Tests use private source/unit files and file-backed Docker/systemd fixtures. The
actual accepted recipes are prepared and rendered read-only on CT100; no production
container replacement or operational rollback proof is claimed.

References: [Compose up](https://docs.docker.com/reference/cli/docker/compose/up/),
[production service updates](https://docs.docker.com/compose/how-tos/production/).
