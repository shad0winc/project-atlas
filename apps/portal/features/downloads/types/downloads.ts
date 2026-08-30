export type DownloadState =
  | "downloading"
  | "queued"
  | "stalled"
  | "paused"
  | "checking"
  | "moving"
  | "seeding"
  | "completed"
  | "error"
  | "unknown";

export type DownloadSummary = Readonly<{
  active: number;
  queued: number;
  completed: number;
  error: number;
  downloadRate: number;
  uploadRate: number;
}>;

export type DownloadItem = Readonly<{
  name: string;
  category: string | null;
  state: DownloadState;
  progress: number;
  totalBytes: number;
  downloadedBytes: number;
  downloadRate: number;
  uploadRate: number;
  etaSeconds: number | null;
}>;

export type DownloadsSnapshot = Readonly<{
  schemaVersion: number;
  generatedAt: string;
  summary: DownloadSummary;
  downloads: readonly DownloadItem[];
}>;

export type DownloadsState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "error"; error: Error }>
  | Readonly<{ status: "ready"; data: DownloadsSnapshot }>;

const DOWNLOAD_STATES = new Set<DownloadState>([
  "downloading",
  "queued",
  "stalled",
  "paused",
  "checking",
  "moving",
  "seeding",
  "completed",
  "error",
  "unknown"
]);

function objectValue(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object.`);
  }
  return value as Record<string, unknown>;
}

function numberValue(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new Error(`${label} must be a non-negative finite number.`);
  }
  return value;
}

function integerValue(value: unknown, label: string): number {
  const result = numberValue(value, label);
  if (!Number.isInteger(result)) {
    throw new Error(`${label} must be an integer.`);
  }
  return result;
}

function stringValue(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${label} must be a non-empty string.`);
  }
  return value;
}

function nullableStringValue(value: unknown, label: string): string | null {
  if (value === null) return null;
  return stringValue(value, label);
}

function nullableIntegerValue(value: unknown, label: string): number | null {
  if (value === null) return null;
  return integerValue(value, label);
}

function downloadStateValue(value: unknown): DownloadState {
  if (typeof value !== "string" || !DOWNLOAD_STATES.has(value as DownloadState)) {
    throw new Error("Download state is invalid.");
  }
  return value as DownloadState;
}

function createDownloadItem(value: unknown): DownloadItem {
  const item = objectValue(value, "Download item");
  const progress = numberValue(item.progress, "Download progress");
  if (progress > 1) {
    throw new Error("Download progress must be between zero and one.");
  }

  return {
    name: stringValue(item.name, "Download name"),
    category: nullableStringValue(item.category, "Download category"),
    state: downloadStateValue(item.state),
    progress,
    totalBytes: integerValue(item.total_bytes, "Download total bytes"),
    downloadedBytes: integerValue(item.downloaded_bytes, "Downloaded bytes"),
    downloadRate: integerValue(item.download_rate, "Download rate"),
    uploadRate: integerValue(item.upload_rate, "Upload rate"),
    etaSeconds: nullableIntegerValue(item.eta_seconds, "Download ETA")
  };
}

export function createDownloadsSnapshot(value: unknown): DownloadsSnapshot {
  const payload = objectValue(value, "Downloads response");
  const summary = objectValue(payload.summary, "Downloads summary");

  if (!Array.isArray(payload.downloads)) {
    throw new Error("Downloads response must contain a downloads array.");
  }

  if (payload.downloads.length > 100) {
    throw new Error("Downloads response exceeds the bounded item contract.");
  }

  return {
    schemaVersion: integerValue(payload.schema_version, "Downloads schema version"),
    generatedAt: stringValue(payload.generated_at, "Downloads generated timestamp"),
    summary: {
      active: integerValue(summary.active, "Active download count"),
      queued: integerValue(summary.queued, "Queued download count"),
      completed: integerValue(summary.completed, "Completed download count"),
      error: integerValue(summary.error, "Download error count"),
      downloadRate: integerValue(summary.total_download_rate, "Aggregate download rate"),
      uploadRate: integerValue(summary.total_upload_rate, "Aggregate upload rate")
    },
    downloads: payload.downloads.map(createDownloadItem)
  };
}
