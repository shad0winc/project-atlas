import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";
import { createDownloadsSnapshot, type DownloadsSnapshot } from "../types/downloads";

export type LoadDownloadsOptions = Readonly<{
  signal?: AbortSignal;
}>;

export async function loadDownloads({ signal }: LoadDownloadsOptions = {}): Promise<DownloadsSnapshot> {
  const response = await authenticatedAtlasApiRequest<unknown>("/downloads", {
    method: "GET",
    cache: "no-store",
    signal
  });

  return createDownloadsSnapshot(response);
}
