# Scheduler observation publication

After `atlas scheduler run` finishes its selected task or due-task batch, the dispatcher publishes the scheduler snapshot while still holding the deployment execution exclusion lock. Publication reads the completed task records; it never registers or reruns a task. Empty due batches also publish an observation. List, inspect, history and dry-run do not publish.

Publication uses the existing atomic Dashboard writer and its root:20000 ownership, 0750 parent and 0640 file permissions. Explicit snapshot/runtime-directory overrides remain supported. The default destination is `runtime/dashboard/scheduler.json` beneath the configured Atlas runtime root. Deployment-time publication shares the same projection code.

The projection retains operational timestamps, status and counts while excluding callbacks and replacing raw task errors with a generic failure message. Publication never rewrites authoritative task records, receipt journals or request state. Task failures retain their nonzero outcome and appear as degraded; Administration maps degraded or disabled tasks to attention. Stale observations remain stale even when the stored status says healthy.

If task execution succeeds but publication fails, the command returns 4 and prints a generic publication error. Completed task outcomes remain persisted. If both execution and publication fail, execution retains exit code 1. Publication failure does not trigger a callback retry or roll back completed tasks. An old snapshot remains old rather than receiving a fabricated fresh timestamp. Investigate publisher access and logs without deleting locks or resetting task records.

Core deployment is required to update the immutable scheduler source generation. Ingress deployment is required for the Administration degraded-status mapping. Preserve existing activation flags and other module sources through both supported transactions. Verify two scheduled publications advancing the snapshot and compare the recorded request-reconciliation timestamp with live task state. A fresh snapshot alone does not prove timer liveness, recovery of uncertain receipts, or successful acquisition.
