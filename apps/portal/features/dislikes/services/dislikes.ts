import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createDislike,
  createDislikeCollection,
  normalizeDislikeId,
  normalizeDislikeUserId,
  type Dislike
} from "../types/dislikes";

export type ReadDislikesOptions = Readonly<{
  expectedUserId: string;
  signal?: AbortSignal;
}>;

export type CreateDislikeOptions = Readonly<{
  expectedUserId: string;
  signal?: AbortSignal;
}>;

export type DislikeCreateInput = Readonly<{
  provider: string;
  itemId: string;
}>;

export type RemoveDislikeOptions = Readonly<{
  expectedUserId: string;
  signal?: AbortSignal;
}>;

type DislikeTransportResponse = Readonly<{
  schema_version: number;
  dislike_id: string;
  user_id: string;
  provider: string;
  item_id: string;
  media_type: string;
  title: string | null;
  metadata: Readonly<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
}>;

type DislikeListTransportResponse = Readonly<{
  dislikes: readonly DislikeTransportResponse[];
}>;

function mapDislike(response: DislikeTransportResponse): Dislike {
  return createDislike({
    schemaVersion: response.schema_version,
    dislikeId: response.dislike_id,
    userId: response.user_id,
    provider: response.provider,
    itemId: response.item_id,
    mediaType: response.media_type,
    ...(response.title === null ? {} : { title: response.title }),
    metadata: response.metadata,
    createdAt: response.created_at,
    updatedAt: response.updated_at
  });
}

export async function createDislikeRecord(
  input: DislikeCreateInput,
  { expectedUserId, signal }: CreateDislikeOptions
): Promise<Dislike> {
  const normalizedUserId = normalizeDislikeUserId(expectedUserId);

  const provider = input.provider.trim().toLowerCase();
  const itemId = input.itemId.trim();

  if (!provider) {
    throw new Error("dislike.provider must not be empty.");
  }

  if (!itemId) {
    throw new Error("dislike.itemId must not be empty.");
  }

  const response = await authenticatedAtlasApiRequest<DislikeTransportResponse>("/dislikes", {
    method: "POST",
    cache: "no-store",
    signal,
    body: {
      provider,
      item_id: itemId
    },
    retryPolicy: {
      maxRetries: 0,
      baseDelayMs: 250,
      maxDelayMs: 5_000
    }
  });

  const created = mapDislike(response);

  if (created.userId !== normalizedUserId) {
    throw new Error("Dislike creation response crossed the authenticated-user boundary.");
  }

  if (created.provider !== provider || created.itemId !== itemId) {
    throw new Error("Dislike creation response did not match the requested media identity.");
  }

  return created;
}

export async function readDislikes({
  expectedUserId,
  signal
}: ReadDislikesOptions): Promise<readonly Dislike[]> {
  const normalizedUserId = normalizeDislikeUserId(expectedUserId);

  const response = await authenticatedAtlasApiRequest<DislikeListTransportResponse>("/dislikes", {
    method: "GET",
    cache: "no-store",
    signal
  });

  return createDislikeCollection(response.dislikes.map(mapDislike), normalizedUserId);
}

export async function removeDislikeRecord(
  dislikeId: string,
  { expectedUserId, signal }: RemoveDislikeOptions
): Promise<Dislike> {
  const normalizedDislikeId = normalizeDislikeId(dislikeId);
  const normalizedUserId = normalizeDislikeUserId(expectedUserId);

  const response = await authenticatedAtlasApiRequest<DislikeTransportResponse>(
    `/dislikes/${encodeURIComponent(normalizedDislikeId)}`,
    {
      method: "DELETE",
      cache: "no-store",
      signal
    }
  );

  const removed = mapDislike(response);

  if (removed.dislikeId !== normalizedDislikeId) {
    throw new Error("Dislikes removal response did not match the requested Dislike.");
  }

  if (removed.userId !== normalizedUserId) {
    throw new Error("Dislikes removal response crossed the authenticated-user boundary.");
  }

  return removed;
}
