import {
  cancelRequestRecord,
  readRequests,
  type CancelRequestOptions,
  type ReadRequestsOptions
} from "../services/requests";

import type { MediaRequest } from "../types/requests";

export type LoadRequestsOptions = ReadRequestsOptions;

export type CancelMediaRequestOptions = CancelRequestOptions;

export async function loadRequests(options: LoadRequestsOptions): Promise<readonly MediaRequest[]> {
  return readRequests(options);
}

export async function cancelMediaRequest(
  requestId: string,
  options: CancelMediaRequestOptions
): Promise<MediaRequest> {
  return cancelRequestRecord(requestId, options);
}
