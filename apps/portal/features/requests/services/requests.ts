import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createMediaRequest,
  createMediaRequestCollection,
  normalizeRequestId,
  normalizeRequestUserId,
  type MediaRequest
} from "../types/requests";

export type ReadRequestsOptions = Readonly<{
  expectedUserId: string;
  signal?: AbortSignal;
}>;

export type CancelRequestOptions = Readonly<{
  expectedUserId: string;
}>;

type MediaRequestTransportResponse = Readonly<{
  request_id: string;
  user_id: string;
  media_type: string;
  provider: string;
  provider_media_id: string;
  title: string;
  year: number | null;
  season_number: number | null;
  status: string;
  terminal: boolean;
  active: boolean;
  can_cancel: boolean;
  recovery_required: boolean;
  created_at: string;
  updated_at: string;
  available_at: string | null;
}>;

type MediaRequestListTransportResponse = Readonly<{
  requests: readonly MediaRequestTransportResponse[];
}>;

type HttpFailureShape = Readonly<{
  status?: unknown;
  detail?: unknown;
  message?: unknown;
}>;

export class RequestCancellationError extends Error {
  readonly reconciliationRequired: boolean;

  constructor(message: string, reconciliationRequired: boolean, options: ErrorOptions = {}) {
    super(message, options);

    this.name = "RequestCancellationError";
    this.reconciliationRequired = reconciliationRequired;
  }
}

function mapMediaRequest(response: MediaRequestTransportResponse): MediaRequest {
  return createMediaRequest({
    requestId: response.request_id,
    userId: response.user_id,
    mediaType: response.media_type as MediaRequest["mediaType"],
    provider: response.provider,
    providerMediaId: response.provider_media_id,
    title: response.title,
    ...(response.year === null ? {} : { year: response.year }),
    ...(response.season_number === null ? {} : { seasonNumber: response.season_number }),
    status: response.status as MediaRequest["status"],
    terminal: response.terminal,
    active: response.active,
    canCancel: response.can_cancel,
    recoveryRequired: response.recovery_required,
    createdAt: response.created_at,
    updatedAt: response.updated_at,
    ...(response.available_at === null ? {} : { availableAt: response.available_at })
  });
}

function failureDetail(error: unknown): string {
  if (error !== null && typeof error === "object") {
    const candidate = error as HttpFailureShape;

    if (typeof candidate.detail === "string" && candidate.detail.trim()) {
      return candidate.detail.trim();
    }

    if (typeof candidate.message === "string" && candidate.message.trim()) {
      return candidate.message.trim();
    }
  }

  return "Atlas did not confirm the cancellation.";
}

function cancellationRequiresReconciliation(error: unknown): boolean {
  if (error === null || typeof error !== "object") {
    return false;
  }

  const candidate = error as HttpFailureShape;

  return (
    candidate.status === 409 &&
    typeof candidate.detail === "string" &&
    candidate.detail.toLowerCase().includes("requires reconciliation") &&
    candidate.detail.includes("Do not retry this request.")
  );
}

function cancellationFailure(error: unknown): RequestCancellationError {
  const reconciliationRequired = cancellationRequiresReconciliation(error);

  const detail = failureDetail(error);

  if (reconciliationRequired) {
    return new RequestCancellationError(
      `${detail} Refresh request status to inspect the latest Atlas state.`,
      true,
      {
        cause: error
      }
    );
  }

  return new RequestCancellationError(
    `${detail} Refresh request status before attempting another cancellation.`,
    false,
    {
      cause: error
    }
  );
}

export async function readRequests({
  expectedUserId,
  signal
}: ReadRequestsOptions): Promise<readonly MediaRequest[]> {
  const normalizedUserId = normalizeRequestUserId(expectedUserId);

  const response = await authenticatedAtlasApiRequest<MediaRequestListTransportResponse>(
    "/requests",
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  return createMediaRequestCollection(response.requests.map(mapMediaRequest), normalizedUserId);
}

export async function cancelRequestRecord(
  requestId: string,
  { expectedUserId }: CancelRequestOptions
): Promise<MediaRequest> {
  const normalizedRequestId = normalizeRequestId(requestId);

  const normalizedUserId = normalizeRequestUserId(expectedUserId);

  let response: MediaRequestTransportResponse;

  try {
    response = await authenticatedAtlasApiRequest<MediaRequestTransportResponse>(
      `/requests/${encodeURIComponent(normalizedRequestId)}/cancel`,
      {
        method: "POST",
        cache: "no-store",

        // A cancellation is a state transition. Never allow the generic
        // transport retry mechanism to repeat it automatically.
        retryPolicy: {
          maxRetries: 0,
          baseDelayMs: 250,
          maxDelayMs: 5_000
        }
      }
    );
  } catch (error: unknown) {
    throw cancellationFailure(error);
  }

  const cancelled = mapMediaRequest(response);

  if (cancelled.requestId !== normalizedRequestId) {
    throw new RequestCancellationError(
      "Cancellation response did not match the requested Atlas Request. Refresh request status before another cancellation.",
      false
    );
  }

  if (cancelled.userId !== normalizedUserId) {
    throw new RequestCancellationError(
      "Cancellation response crossed the authenticated-user boundary. Refresh request status before another cancellation.",
      false
    );
  }

  if (cancelled.status !== "cancelled") {
    throw new RequestCancellationError(
      "Atlas did not return a cancelled lifecycle state. Refresh request status before another cancellation.",
      false
    );
  }

  return cancelled;
}
