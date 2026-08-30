"use client";

import { useState } from "react";

import { Card } from "../../../components/ui/Card";
import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";
import { useDownloads } from "../../downloads/hooks/use-downloads";
import type { DownloadItem } from "../../downloads/types/downloads";
import { runDownloadManagementAction, type DownloadManagementAction } from "../api/actions";

function actionLabel(action: DownloadManagementAction): string {
  if (action === "stop_seeding") return "Stop seeding";
  if (action === "resume") return "Resume";
  return "Remove job";
}

function DownloadJobControls({ item, busy, onAction }: Readonly<{
  item: DownloadItem;
  busy: boolean;
  onAction: (item: DownloadItem, action: DownloadManagementAction) => void;
}>): React.ReactElement {
  const normalizedState = item.state.toLowerCase();
  const canStop = normalizedState === "seeding" || normalizedState === "queued";
  const canResume = normalizedState === "paused" || normalizedState === "completed";
  const canRemove =
    normalizedState === "completed" ||
    normalizedState === "seeding" ||
    normalizedState === "queued" ||
    normalizedState === "paused";
  return (
    <div className="request-card-actions">
      <button className="button button--secondary" disabled={busy || !canStop} onClick={() => onAction(item, "stop_seeding")} type="button">Stop seeding</button>
      <button className="button button--secondary" disabled={busy || !canResume} onClick={() => onAction(item, "resume")} type="button">Resume</button>
      <button className="button button--secondary" disabled={busy || !canRemove} onClick={() => onAction(item, "remove_job")} type="button">Remove job</button>
    </div>
  );
}

export function DownloadManagementView(): React.ReactElement {
  const { can } = usePermission();
  const { state, refresh } = useDownloads();
  const [busyJobId, setBusyJobId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  if (!can(ATLAS_PERMISSIONS.downloadsManage)) {
    return <Card><h3>Download management unavailable</h3><p role="alert">Your account does not have permission to manage download jobs.</p></Card>;
  }

  async function onAction(item: DownloadItem, action: DownloadManagementAction): Promise<void> {
    if (busyJobId !== null) return;
    const confirmation = action !== "remove_job" || window.confirm(`Remove the completed job for “${item.name}”? Downloaded media will be kept.`);
    if (!confirmation) return;
    setBusyJobId(item.jobId);
    setMessage(null);
    try {
      await runDownloadManagementAction(item.jobId, action);
      setMessage(`${actionLabel(action)} accepted for ${item.name}.`);
      refresh();
    } catch {
      setMessage(`Atlas could not ${actionLabel(action).toLowerCase()} for ${item.name}. Refresh before retrying.`);
    } finally {
      setBusyJobId(null);
    }
  }

  if (state.status === "loading") return <Card><p aria-live="polite">Loading download management…</p></Card>;
  if (state.status === "error") return <Card><h3>Download management unavailable</h3><p role="alert">{state.error.message}</p><button className="button button--secondary" onClick={refresh} type="button">Try again</button></Card>;

  return (
    <section aria-labelledby="download-management-title">
      <Card className="download-management-card">
        <h3 id="download-management-title">Download job controls</h3>
        <p>These controls change qBittorrent job state only. Remove job keeps downloaded media. Atlas media-retention rules remain separate.</p>
        {message ? <p aria-live="polite">{message}</p> : null}
      </Card>
      <div className="request-card-list" style={{ marginTop: "1rem" }}>
        {state.data.downloads.length === 0 ? <Card><h4>No download jobs</h4><p>The runtime snapshot contains no jobs to manage.</p></Card> : state.data.downloads.map((item) => (
          <Card className="download-management-card" key={item.jobId}>
            <div className="administration-card-content">
              <p className="portal-page-eyebrow">{item.category ?? "Uncategorized"}</p>
              <h4>{item.name}</h4>
              <p>State: {item.state}</p>
            </div>
            <DownloadJobControls busy={busyJobId !== null} item={item} onAction={onAction} />
          </Card>
        ))}
      </div>
    </section>
  );
}
