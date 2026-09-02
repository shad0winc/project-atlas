import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type DownloadManagementAction = "stop_seeding" | "resume" | "remove_job";

export type DownloadManagementResult = Readonly<{
  accepted: boolean;
  action: DownloadManagementAction;
  jobId: string;
}>;

type DownloadManagementTransport = Readonly<{
  status: "accepted";
  action: DownloadManagementAction;
  job_id: string;
}>;

function normalizeJobId(jobId: string): string {
  const normalized = jobId.trim();
  if (!/^dl_[0-9a-f]{32}$/.test(normalized)) {
    throw new Error("Download job identifier is invalid. Refresh download activity before retrying.");
  }
  return normalized;
}

export async function runDownloadManagementAction(
  jobId: string,
  action: DownloadManagementAction
): Promise<DownloadManagementResult> {
  const normalizedJobId = normalizeJobId(jobId);
  const response = await authenticatedAtlasApiRequest<DownloadManagementTransport>(
    "/admin/downloads/action",
    {
      method: "POST",
      cache: "no-store",
      body: { job_id: normalizedJobId, action },
      retryPolicy: { maxRetries: 0, baseDelayMs: 250, maxDelayMs: 5_000 }
    }
  );

  if (
    response.status !== "accepted" ||
    response.action !== action ||
    response.job_id !== normalizedJobId
  ) {
    throw new Error("Download management response did not match the requested action. Refresh before retrying.");
  }

  return { accepted: true, action: response.action, jobId: response.job_id };
}
