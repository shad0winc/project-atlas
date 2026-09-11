export type DislikeMetadata = Readonly<Record<string, unknown>>;

export type Dislike = Readonly<{
  schemaVersion: number;
  dislikeId: string;
  userId: string;
  provider: string;
  itemId: string;
  mediaType: string;
  title?: string;
  metadata: DislikeMetadata;
  createdAt: string;
  updatedAt: string;
}>;

export type DislikesLoadingState = Readonly<{
  status: "loading";
}>;

export type DislikesReadyState = Readonly<{
  status: "ready";
  data: readonly Dislike[];
}>;

export type DislikesErrorState = Readonly<{
  status: "error";
  error: Error;
}>;

export type DislikesState = DislikesLoadingState | DislikesReadyState | DislikesErrorState;

const DISLIKE_ID_PATTERN = /^dis_[a-f0-9]{32}$/;
const USER_ID_PATTERN = /^usr_[a-f0-9]{32}$/;

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

function normalizeOptionalText(value: string | undefined): string | undefined {
  const normalized = value?.trim();

  return normalized ? normalized : undefined;
}

function normalizeSchemaVersion(value: number): number {
  if (!Number.isInteger(value) || value < 1) {
    throw new Error("dislike.schemaVersion must be a positive integer.");
  }

  return value;
}

function normalizeMetadata(metadata: DislikeMetadata): DislikeMetadata {
  if (metadata === null || typeof metadata !== "object" || Array.isArray(metadata)) {
    throw new Error("dislike.metadata must be an object.");
  }

  return Object.freeze({
    ...metadata
  });
}

export function normalizeDislikeId(value: string): string {
  return normalizeIdentity(value, "dislike.dislikeId", DISLIKE_ID_PATTERN);
}

export function normalizeDislikeUserId(value: string): string {
  return normalizeIdentity(value, "dislike.userId", USER_ID_PATTERN);
}

export function createDislike(dislike: Dislike): Dislike {
  const createdAt = normalizeTimestamp(dislike.createdAt, "dislike.createdAt");
  const updatedAt = normalizeTimestamp(dislike.updatedAt, "dislike.updatedAt");
  const title = normalizeOptionalText(dislike.title);

  return Object.freeze({
    schemaVersion: normalizeSchemaVersion(dislike.schemaVersion),
    dislikeId: normalizeDislikeId(dislike.dislikeId),
    userId: normalizeDislikeUserId(dislike.userId),
    provider: normalizeRequiredText(dislike.provider, "dislike.provider").toLowerCase(),
    itemId: normalizeRequiredText(dislike.itemId, "dislike.itemId"),
    mediaType: normalizeRequiredText(dislike.mediaType, "dislike.mediaType").toLowerCase(),
    ...(title === undefined ? {} : { title }),
    metadata: normalizeMetadata(dislike.metadata),
    createdAt,
    updatedAt
  });
}

export function createDislikeCollection(
  dislikes: readonly Dislike[],
  expectedUserId?: string
): readonly Dislike[] {
  const normalized = dislikes.map(createDislike);

  const dislikeIds = new Set(normalized.map((dislike) => dislike.dislikeId));

  if (dislikeIds.size !== normalized.length) {
    throw new Error("Dislike IDs must be unique.");
  }

  const mediaIdentities = new Set(
    normalized.map(
      (dislike) => `${dislike.userId}\u0000${dislike.provider}\u0000${dislike.itemId}`
    )
  );

  if (mediaIdentities.size !== normalized.length) {
    throw new Error("Dislike media identities must be unique.");
  }

  const ownerUserId =
    expectedUserId === undefined ? normalized[0]?.userId : normalizeDislikeUserId(expectedUserId);

  if (ownerUserId && normalized.some((dislike) => dislike.userId !== ownerUserId)) {
    throw new Error("Dislikes response crossed the authenticated-user boundary.");
  }

  return Object.freeze(normalized);
}

export function createDislikesState(
  data: readonly Dislike[] | null,
  error: Error | null
): DislikesState {
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
