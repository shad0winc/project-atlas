export const MEDIA_REQUEST_TYPES = ["movie", "tv", "anime_movie", "anime_tv", "sports"] as const;

export type MediaRequestType = (typeof MEDIA_REQUEST_TYPES)[number];

export const MEDIA_REQUEST_STATUSES = [
  "pending",
  "submitting",
  "approved",
  "searching",
  "downloading",
  "importing",
  "available",
  "rejected",
  "failed",
  "cancelling",
  "cancelled"
] as const;

export type MediaRequestStatus = (typeof MEDIA_REQUEST_STATUSES)[number];

export type MediaRequest = Readonly<{
  requestId: string;
  userId: string;
  mediaType: MediaRequestType;
  provider: string;
  providerMediaId: string;
  title: string;
  year?: number;
  seasonNumber?: number;
  status: MediaRequestStatus;
  terminal: boolean;
  active: boolean;
  canCancel: boolean;
  recoveryRequired: boolean;
  createdAt: string;
  updatedAt: string;
  availableAt?: string;
}>;

export type MediaRequestCreateInput = Readonly<{
  mediaType: MediaRequestType;
  providerMediaId: string;
  title: string;
  year?: number;
  seasonNumber?: number;
}>;

export type RequestsLoadingState = Readonly<{
  status: "loading";
}>;

export type RequestsReadyState = Readonly<{
  status: "ready";
  data: readonly MediaRequest[];
}>;

export type RequestsErrorState = Readonly<{
  status: "error";
  error: Error;
}>;

export type RequestsState = RequestsLoadingState | RequestsReadyState | RequestsErrorState;

const REQUEST_ID_PATTERN = /^req_[a-f0-9]{32}$/;
const USER_ID_PATTERN = /^usr_[a-f0-9]{32}$/;

const REQUEST_TYPE_SET = new Set<string>(MEDIA_REQUEST_TYPES);
const REQUEST_STATUS_SET = new Set<string>(MEDIA_REQUEST_STATUSES);

const TERMINAL_STATUSES = new Set<MediaRequestStatus>([
  "available",
  "rejected",
  "failed",
  "cancelled"
]);

const RECOVERY_REQUIRED_STATUSES = new Set<MediaRequestStatus>(["submitting", "cancelling"]);

function normalizeRequiredText(value: string, fieldName: string): string {
  const normalized = value.trim();

  if (!normalized) {
    throw new Error(`${fieldName} must not be empty.`);
  }

  return normalized;
}

function normalizeIdentity(value: string, fieldName: string, pattern: RegExp): string {
  const normalized = normalizeRequiredText(value, fieldName).toLowerCase();

  if (!pattern.test(normalized)) {
    throw new Error(`${fieldName} is invalid.`);
  }

  return normalized;
}

function normalizeTimestamp(value: string, fieldName: string): string {
  const normalized = normalizeRequiredText(value, fieldName);
  const timestamp = new Date(normalized);

  if (Number.isNaN(timestamp.getTime())) {
    throw new Error(`${fieldName} must be a valid timestamp.`);
  }

  return timestamp.toISOString();
}

function normalizeOptionalTimestamp(
  value: string | undefined,
  fieldName: string
): string | undefined {
  if (value === undefined) {
    return undefined;
  }

  return normalizeTimestamp(value, fieldName);
}

function normalizeOptionalInteger(
  value: number | undefined,
  fieldName: string,
  minimum: number
): number | undefined {
  if (value === undefined) {
    return undefined;
  }

  if (!Number.isInteger(value) || value < minimum) {
    throw new Error(`${fieldName} is invalid.`);
  }

  return value;
}

function normalizeMediaType(value: string): MediaRequestType {
  const normalized = normalizeRequiredText(value, "request.mediaType")
    .toLowerCase()
    .replace(/-/g, "_");

  if (!REQUEST_TYPE_SET.has(normalized)) {
    throw new Error("request.mediaType is invalid.");
  }

  return normalized as MediaRequestType;
}

function normalizeStatus(value: string): MediaRequestStatus {
  const normalized = normalizeRequiredText(value, "request.status")
    .toLowerCase()
    .replace(/-/g, "_");

  if (!REQUEST_STATUS_SET.has(normalized)) {
    throw new Error("request.status is invalid.");
  }

  return normalized as MediaRequestStatus;
}

export function normalizeRequestId(value: string): string {
  return normalizeIdentity(value, "request.requestId", REQUEST_ID_PATTERN);
}

export function normalizeRequestUserId(value: string): string {
  return normalizeIdentity(value, "request.userId", USER_ID_PATTERN);
}

export function createMediaRequestInput(input: MediaRequestCreateInput): MediaRequestCreateInput {
  const mediaType = normalizeMediaType(input.mediaType);

  const providerMediaId = normalizeRequiredText(input.providerMediaId, "request.providerMediaId");

  const title = normalizeRequiredText(input.title, "request.title");

  const year = normalizeOptionalInteger(input.year, "request.year", 1888);

  const seasonNumber = normalizeOptionalInteger(input.seasonNumber, "request.seasonNumber", 0);

  if (seasonNumber !== undefined && mediaType !== "tv" && mediaType !== "anime_tv") {
    throw new Error("request.seasonNumber is valid only for TV requests.");
  }

  return Object.freeze({
    mediaType,
    providerMediaId,
    title,
    ...(year === undefined ? {} : { year }),
    ...(seasonNumber === undefined ? {} : { seasonNumber })
  });
}

export function createMediaRequest(request: MediaRequest): MediaRequest {
  const requestId = normalizeRequestId(request.requestId);
  const userId = normalizeRequestUserId(request.userId);
  const mediaType = normalizeMediaType(request.mediaType);
  const status = normalizeStatus(request.status);

  const provider = normalizeRequiredText(request.provider, "request.provider").toLowerCase();
  const providerMediaId = normalizeRequiredText(request.providerMediaId, "request.providerMediaId");
  const title = normalizeRequiredText(request.title, "request.title");

  const year = normalizeOptionalInteger(request.year, "request.year", 1888);
  const seasonNumber = normalizeOptionalInteger(request.seasonNumber, "request.seasonNumber", 0);

  if (seasonNumber !== undefined && mediaType !== "tv" && mediaType !== "anime_tv") {
    throw new Error("request.seasonNumber is valid only for TV requests.");
  }

  const createdAt = normalizeTimestamp(request.createdAt, "request.createdAt");
  const updatedAt = normalizeTimestamp(request.updatedAt, "request.updatedAt");
  const availableAt = normalizeOptionalTimestamp(request.availableAt, "request.availableAt");

  if (new Date(updatedAt).getTime() < new Date(createdAt).getTime()) {
    throw new Error("request.updatedAt cannot be earlier than request.createdAt.");
  }

  const expectedTerminal = TERMINAL_STATUSES.has(status);
  const expectedRecoveryRequired = RECOVERY_REQUIRED_STATUSES.has(status);

  if (request.terminal !== expectedTerminal) {
    throw new Error("request.terminal does not match request.status.");
  }

  if (request.active === request.terminal) {
    throw new Error("request.active does not match request.terminal.");
  }

  if (request.recoveryRequired !== expectedRecoveryRequired) {
    throw new Error("request.recoveryRequired does not match request.status.");
  }

  if (request.canCancel && (request.terminal || request.recoveryRequired)) {
    throw new Error("request.canCancel conflicts with request lifecycle state.");
  }

  if (status === "available" && availableAt === undefined) {
    throw new Error("request.availableAt is required for available requests.");
  }

  return Object.freeze({
    requestId,
    userId,
    mediaType,
    provider,
    providerMediaId,
    title,
    ...(year === undefined ? {} : { year }),
    ...(seasonNumber === undefined ? {} : { seasonNumber }),
    status,
    terminal: request.terminal,
    active: request.active,
    canCancel: request.canCancel,
    recoveryRequired: request.recoveryRequired,
    createdAt,
    updatedAt,
    ...(availableAt === undefined ? {} : { availableAt })
  });
}

export function createMediaRequestCollection(
  requests: readonly MediaRequest[],
  expectedUserId?: string
): readonly MediaRequest[] {
  const normalized = requests.map(createMediaRequest);

  const requestIds = new Set(normalized.map((request) => request.requestId));

  if (requestIds.size !== normalized.length) {
    throw new Error("Media Request IDs must be unique.");
  }

  const ownerUserId =
    expectedUserId === undefined ? normalized[0]?.userId : normalizeRequestUserId(expectedUserId);

  if (ownerUserId && normalized.some((request) => request.userId !== ownerUserId)) {
    throw new Error("Media Requests response crossed the authenticated-user boundary.");
  }

  return Object.freeze(normalized);
}

export function replaceMediaRequest(
  requests: readonly MediaRequest[],
  replacement: MediaRequest,
  expectedUserId: string
): readonly MediaRequest[] {
  const normalizedReplacement = createMediaRequest(replacement);
  const normalizedUserId = normalizeRequestUserId(expectedUserId);

  if (normalizedReplacement.userId !== normalizedUserId) {
    throw new Error("Media Request replacement crossed the authenticated-user boundary.");
  }

  let replaced = false;

  const next = requests.map((request) => {
    if (request.requestId !== normalizedReplacement.requestId) {
      return request;
    }

    replaced = true;
    return normalizedReplacement;
  });

  if (!replaced) {
    throw new Error("Media Request replacement did not match the loaded collection.");
  }

  return createMediaRequestCollection(next, normalizedUserId);
}

export function createRequestsState(
  data: readonly MediaRequest[] | null,
  error: Error | null
): RequestsState {
  if (error) {
    return {
      status: "error",
      error
    };
  }

  if (data !== null) {
    return {
      status: "ready",
      data
    };
  }

  return {
    status: "loading"
  };
}
