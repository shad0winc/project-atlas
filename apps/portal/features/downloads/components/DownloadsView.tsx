"use client";

import { useDownloads } from "../hooks/use-downloads";
import type { DownloadItem, DownloadState, DownloadsSnapshot, DownloadsState } from "../types/downloads";

const STATE_LABELS: Readonly<Record<DownloadState, string>> = {
  downloading: "Downloading",
  queued: "Queued",
  stalled: "Stalled",
  paused: "Paused",
  checking: "Checking",
  moving: "Moving",
  seeding: "Seeding",
  completed: "Completed",
  error: "Error",
  unknown: "Unknown"
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KiB", "MiB", "GiB", "TiB"] as const;
  let value = bytes / 1024;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value >= 100 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

function formatRate(bytesPerSecond: number): string {
  return bytesPerSecond === 0 ? "0 B/s" : `${formatBytes(bytesPerSecond)}/s`;
}

function formatEta(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  if (hours < 24) return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
  const days = Math.floor(hours / 24);
  const remainingHours = hours % 24;
  return remainingHours ? `${days}d ${remainingHours}h` : `${days}d`;
}

function generatedTime(timestamp: string): string {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return timestamp;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(parsed);
}

function SummaryCard({ label, value }: Readonly<{ label: string; value: string | number }>): React.ReactElement {
  return (
    <article className="dashboard-metric-card">
      <p className="dashboard-metric-label">{label}</p>
      <p className="dashboard-metric-value">{value}</p>
    </article>
  );
}

function DownloadCard({ item }: Readonly<{ item: DownloadItem }>): React.ReactElement {
  const percent = Math.round(item.progress * 100);

  return (
    <article className="request-card">
      <header className="request-card-header">
        <div>
          <p className="request-card-kind">{item.category ?? "Uncategorized"}</p>
          <h3 className="request-card-title">{item.name}</h3>
        </div>
        <span className="request-status-badge" data-status={item.state}>
          {STATE_LABELS[item.state]}
        </span>
      </header>

      <div>
        <label htmlFor={`download-progress-${item.name}`}>
          Progress {percent}%
        </label>
        <progress
          id={`download-progress-${item.name}`}
          max={100}
          value={percent}
          style={{ width: "100%" }}
        >
          {percent}%
        </progress>
      </div>

      <dl className="request-card-meta">
        <div><dt>Downloaded</dt><dd>{formatBytes(item.downloadedBytes)} / {formatBytes(item.totalBytes)}</dd></div>
        <div><dt>Download rate</dt><dd>{formatRate(item.downloadRate)}</dd></div>
        <div><dt>Upload rate</dt><dd>{formatRate(item.uploadRate)}</dd></div>
        <div><dt>ETA</dt><dd>{formatEta(item.etaSeconds)}</dd></div>
      </dl>
    </article>
  );
}

function DownloadsReady({ snapshot, refresh }: Readonly<{ snapshot: DownloadsSnapshot; refresh: () => void }>): React.ReactElement {
  return (
    <section aria-label="Download activity">
      <div className="dashboard-metric-grid">
        <SummaryCard label="Active" value={snapshot.summary.active} />
        <SummaryCard label="Queued" value={snapshot.summary.queued} />
        <SummaryCard label="Completed" value={snapshot.summary.completed} />
        <SummaryCard label="Errors" value={snapshot.summary.error} />
        <SummaryCard label="Download rate" value={formatRate(snapshot.summary.downloadRate)} />
        <SummaryCard label="Upload rate" value={formatRate(snapshot.summary.uploadRate)} />
      </div>

      <div className="request-card-actions" style={{ marginBlock: "1rem" }}>
        <p>Snapshot generated {generatedTime(snapshot.generatedAt)}</p>
        <button className="request-secondary-button" onClick={refresh} type="button">Refresh</button>
      </div>

      {snapshot.downloads.length === 0 ? (
        <section className="dashboard-error">
          <div>
            <p>Downloads</p>
            <h3>No download activity</h3>
            <p>Atlas has a valid runtime snapshot and there are no downloads to display.</p>
          </div>
        </section>
      ) : (
        <div className="request-card-list">
          {snapshot.downloads.map((item, index) => (
            <DownloadCard item={item} key={`${item.name}-${item.category ?? ""}-${index}`} />
          ))}
        </div>
      )}
    </section>
  );
}

export function DownloadsContent({
  state,
  refresh
}: Readonly<{ state: DownloadsState; refresh: () => void }>): React.ReactElement {
  if (state.status === "loading") {
    return (
      <section aria-busy="true" aria-label="Loading download activity" className="dashboard-metric-grid">
        {Array.from({ length: 6 }, (_, index) => (
          <div aria-hidden="true" className="dashboard-skeleton-card" key={index} />
        ))}
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section aria-labelledby="downloads-error-title" className="dashboard-error" role="alert">
        <div>
          <p>Downloads unavailable</p>
          <h3 id="downloads-error-title">Atlas could not load download activity</h3>
          <p>{state.error.message}</p>
        </div>
        <button className="dashboard-retry-button" onClick={refresh} type="button">Try again</button>
      </section>
    );
  }

  return <DownloadsReady refresh={refresh} snapshot={state.data} />;
}

export function DownloadsView(): React.ReactElement {
  const { state, refresh } = useDownloads();
  return <DownloadsContent refresh={refresh} state={state} />;
}
