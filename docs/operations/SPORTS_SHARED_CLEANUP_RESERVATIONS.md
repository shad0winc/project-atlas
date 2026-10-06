# Shared Sports cleanup reservations

Shared upstream capacity is a physical resource reservation. A heartbeat timeout
is not proof of upstream closure. Shared leases remain recorded across timeout,
restart, and disabled sharing configuration. A stale shared consumer blocks new
joins to its group until owned cleanup is reconciled. Heartbeat cannot revive an
expired shared lease. Existing exclusive lease expiry behavior is unchanged.

The API preserves both session linkage and shared resource reservations when
live-session resolution fails. Failures may leave an opening or blocked owned
Jellyfin stream receipt; returning a reservation would admit another upstream
while the earlier outcome remains unknown. These failures return a generic 503.
Successful owned cleanup must precede explicit lease release. Unknown cleanup
must not be retried blindly or bypassed by removing JSON records.

This patch does not enable sharing or add automatic reconciliation. A held
reservation can therefore require operator reconciliation. The associated admission canary is described in SPORTS_SHARED_ADMISSION_CANARY.md.
Physical two-viewer/stop-isolation acceptance remains outstanding. Current
exclusive production sessions must not be adopted into a shared generation.

No provider capacity increase, runtime migration, account provisioning, feed
registration, or production deployment is performed by the review runners.
