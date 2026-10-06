"use client";
import { Card } from "../../../components/ui/Card";
import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";
import { useAutomationHealth } from "../hooks/use-automation-health";

export function AutomationHealthPanel(): React.ReactElement | null {
  const { can } = usePermission();
  const allowed = can(ATLAS_PERMISSIONS.systemHealthRead);
  const { state, refresh } = useAutomationHealth(allowed);
  if (!allowed) return null;
  return (
    <section aria-labelledby="automation-health-title">
      <div className="administration-surface-heading">
        <h3 id="automation-health-title">Automation health</h3>
        <p>Review request recovery and acquisition settings, outstanding work, and scheduled reconciliation.</p>
      </div>
      <button className="button button--secondary" type="button" onClick={refresh} disabled={state.status === "loading"}>
        Refresh health
      </button>
      {state.status === "loading" && <p role="status">Loading automation health…</p>}
      {state.status === "error" && <p role="alert">Automation health is unavailable. Refresh to check again.</p>}
      {state.status === "ready" && <>
        <p>Observed at {state.report.observed_at}. Refresh for a current observation.</p>
        <div className="administration-grid">
          <Card className="administration-card">
            <h4>API settings</h4>
            <p>Receipt recovery: {state.report.api_configuration.receipt_recovery}</p>
            <p>Acquisition routing: {state.report.api_configuration.acquisition_routing}</p>
            <p>These settings describe the current API process.</p>
          </Card>
          <Card className="administration-card">
            <h4>Request journal</h4>
            {state.report.request_registry.status === "unavailable" ? <p>Journal observation unavailable.</p> : <>
              <p>Schema: {state.report.request_registry.schema_version}</p>
              <p>Requests: {state.report.request_registry.request_count}</p>
              {state.report.request_registry.schema_version === 2 && <>
                <p>Unresolved submissions: {state.report.request_registry.unresolved_submission_count}</p>
                <p>Receipts awaiting binding: {state.report.request_registry.observed_receipt_count}</p>
                <p>Events awaiting publication: {state.report.request_registry.pending_event_count}</p>
              </>}
            </>}
            <p>Counts describe stored records. Uncertain submissions require reconciliation before another attempt.</p>
          </Card>
          <Card className="administration-card">
            <h4>Scheduled request reconciliation</h4>
            <p>Status: {state.report.request_reconciliation.status}</p>
            {state.report.request_reconciliation.last_success && <p>Last success: {state.report.request_reconciliation.last_success}</p>}
            {state.report.request_reconciliation.consecutive_failures !== undefined && <p>Consecutive failures: {state.report.request_reconciliation.consecutive_failures}</p>}
            <p>Observations older than five minutes are marked stale.</p>
          </Card>
        </div>
        <p>A healthy scheduled pass or an enabled setting does not establish successful receipt recovery, imported audio or subtitles, or live upstream sharing.</p>
      </>}
    </section>
  );
}
