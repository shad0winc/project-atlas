import {
  cancelRequestRecord,
  createRequestRecord,
  readRequests,
  type CancelRequestOptions,
  type CreateRequestOptions,
  type ReadRequestsOptions
} from "../services/requests";

import type { MediaRequest, MediaRequestCreateInput } from "../types/requests";

export type LoadRequestsOptions = ReadRequestsOptions;

export type CancelMediaRequestOptions = CancelRequestOptions;

export type CreatePersonalMediaRequestOptions = CreateRequestOptions;

export async function createPersonalMediaRequest(
  input: MediaRequestCreateInput,
  options: CreatePersonalMediaRequestOptions
): Promise<MediaRequest> {
  return createRequestRecord(input, options);
}

export async function loadRequests(options: LoadRequestsOptions): Promise<readonly MediaRequest[]> {
  return readRequests(options);
}

export async function cancelMediaRequest(
  requestId: string,
  options: CancelMediaRequestOptions
): Promise<MediaRequest> {
  return cancelRequestRecord(requestId, options);
}
