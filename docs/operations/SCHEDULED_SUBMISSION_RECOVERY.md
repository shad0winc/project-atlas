# Scheduled submission recovery — explicit opt-in

The existing `requests.reconcile` callback gains an optional receipt recovery
and submission outbox pass. `ATLAS_SUBMISSION_RECOVERY_ENABLED` defaults to `0`;
only `0` and `1` are accepted. No configuration is changed by this patch. Schema
1 remains the production contract. Enabling the flag against schema 1 fails
before recovery or readiness work. Explicit schema migration, verified routing
and live lifecycle proof remain separate release gates.

With the flag set to `1` and an explicitly migrated schema-2 service, the callback
prepares readiness dependencies, considers at most 10 recovery-required records,
then attempts at most 25 pending submission events, then performs the existing
normal status/readiness reconciliation. Existing default-off return values and
JSON summaries remain unchanged. Opt-in summaries add receipt outcome counts,
actual publication attempts, acknowledgements and the observed pending count.

Receipt-free requests remain blocked for operator correlation. This callback
never submits a POST or removes an intent. Known receipt recovery uses the
existing native GET/profile verification and guarded binding. A repository or
verification error for one item does not consume later items' opportunities
within the selected batch. Infrastructure errors remain failures; sensitive
recovery exception details are not printed.

The helpers permit limits from 1 through 100 and nonnegative integer offsets;
bool/float values are rejected. Each callback derives separate rotation offsets
from UTC minutes times the respective limit. For a stable backlog, successive
minute selections cover items beyond a permanently unverified prefix. Repeated
calls in the same minute select the same window. Changing backlog membership,
clock changes or missed scheduler invocations do not guarantee strict fairness.
No cursor or recovery evidence is rewritten to perform selection.

Limits bound item attempts, not wall-clock duration or the repository's existing
whole-document read. Native transport/profile timeouts still apply. Journal
publication retains PR255's 16 KiB record and 64 MiB journal limits; pending work
is not silently rotated, repaired, cleared or acknowledged on failure. Different
consumers may change pending counts concurrently. Event publication failures
retain outbox records, and ordinary status reconciliation can continue; this
does not promise global event ordering or exactly-once external notification
delivery. Direct service drains now default to at most 100 items and expose their
last pass's actual attempt count.

Before a future activation: reconcile registry inventory and unresolved POST
barriers, verify native IDs/profiles and journal access/lifecycle budget, preserve
an explicit migration backup, deploy matching consumer generations, then perform
scoped native delayed receipt/restart/imported-media proof. Do not set the flag
or migrate merely because these synthetic tests pass. Sports admission, episode
retention and release reset remain untouched and separately gated.
