# Sports registry ownership during recovery

The API owns its session and Jellyfin live-stream registries. A privileged operator recovering an uncertain open must preserve the existing registry UID and GID when atomically replacing either file. Both writers retain private mode 0600; recovery evidence belongs to the operator and stays separate.

Root-created temporary files previously replaced API-owned registries during recovery. The API then returned `Live session admission is unavailable` because it could no longer read the session registry. Preserve owner and group on the temporary file before publishing the replacement. If ownership transfer fails, retain the original registry and stop recovery.

New registries continue to belong to their creating process. An already incorrect owner requires a scoped, journaled operator repair. Recovery completion must verify registry readability as the API user before reopening admission. Empty records and native counters alone are insufficient proof of physical upstream closure.
