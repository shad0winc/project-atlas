"use client";
import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";
import { useSportsSessionObservation } from "../hooks/use-sports-session-observation";

export function SportsSessionStatus(): React.ReactElement | null {
  const { can } = usePermission();
  const allowed = can(ATLAS_PERMISSIONS.liveSessionsManage);
  const { state, refresh } = useSportsSessionObservation(allowed);
  if (!allowed) return null;
  return <section aria-labelledby="sports-session-status-title">
    <div className="administration-surface-heading">
      <h3 id="sports-session-status-title">Sports live sessions</h3>
      <p>Review recent heartbeats and retained sessions that may prevent another feed from opening.</p>
    </div>
    <button className="button button--secondary" type="button" onClick={refresh}
      disabled={state.status === "loading"}>Refresh session status</button>
    {state.status === "loading" && <p role="status">Loading Sports sessions…</p>}
    {state.status === "error" && <p role="alert">Sports session status is unavailable. Refresh to check again.</p>}
    {state.status === "ready" && <>
      <p>Observed at {state.report.observed_at}. Refresh for a current observation.</p>
      <p>{state.report.recent_count} recent heartbeat / {state.report.expired_count} expired heartbeat / {state.report.retained_count} retained total</p>
      {state.report.retained_count === 0 ? <p>No retained Sports sessions.</p> : <ul>
        {state.report.sessions.map(row => <li key={row.session_id}>
          <strong>{row.target_id}</strong>
          <p>Viewer {row.user_id}; session {row.session_id}</p>
          <p>Last heartbeat {row.heartbeat_age_seconds} seconds ago — {row.heartbeat_expired ? "Expired heartbeat; recovery review needed" : "Recent heartbeat"}</p>
        </li>)}
      </ul>}
      <p>An expired heartbeat does not prove playback has stopped. Refresh only reads status; releasing retained ownership requires verified recovery.</p>
    </>}
  </section>;
}
