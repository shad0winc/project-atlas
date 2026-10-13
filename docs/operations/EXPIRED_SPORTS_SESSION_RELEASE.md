# Explicit release of an expired Sports session

Explicit owned session release must return the recorded resource lease linkage even if the session heartbeat has expired. Pruning that row first caused the authenticated DELETE route to return 404 and leave its shared lease allocated. Release now validates the stored owner, returns the exact record and removes only that session. Unrelated expired rows remain unchanged by this operation.

The API still performs stream ownership cleanup before session and resource release. If stream cleanup is uncertain, the route fails closed and retains the session and lease. This change does not authorize unauthenticated cleanup, expire shared leases by time alone, or change admission and heartbeat expiry. A record already pruned by another operation cannot be recovered by this method.

Authentication expiry can prevent the browser's best-effort DELETE request from reaching this route. Automatic reconciliation and retry after authentication restoration remain separate work. Intermittent HLS buffering is also a separate investigation. Do not treat this change as a complete fix for either issue.
