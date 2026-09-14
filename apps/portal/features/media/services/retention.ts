import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createMediaRetention,
  type MediaRetention,
  type MediaRetentionLifecycleRule,
  type MediaRetentionLifecycleState
} from "../types/retention";

type MediaRetentionTransportResponse = Readonly<{
  provider: string;
  item_id: string;
  eligible: boolean;
  retained: boolean;
  lifecycle: Readonly<{
    state: MediaRetentionLifecycleState;
    rule: MediaRetentionLifecycleRule;
    basis_at: string | null;
    delete_at: string | null;
  }>;
}>;

function normalizeRequiredIdentity(
  value: string,
  field: string
): string {
  const normalized = value.trim();

  if (normalized.length === 0) {
    throw new Error(`${field} must not be empty.`);
  }

  return normalized;
}

function mapMediaRetention(
  response: MediaRetentionTransportResponse
): MediaRetention {
  return createMediaRetention({
    provider: response.provider,
    itemId: response.item_id,
    eligible: response.eligible,
    retained: response.retained,
    lifecycle: {
      state: response.lifecycle.state,
      rule: response.lifecycle.rule,
      basisAt: response.lifecycle.basis_at,
      deleteAt: response.lifecycle.delete_at
    }
  });
}

export async function readMediaRetention(
  provider: string,
  itemId: string,
  signal?: AbortSignal
): Promise<MediaRetention> {
  const normalizedProvider = normalizeRequiredIdentity(
    provider,
    "retention.provider"
  ).toLowerCase();

  const normalizedItemId = normalizeRequiredIdentity(
    itemId,
    "retention.itemId"
  );

  const response =
    await authenticatedAtlasApiRequest<MediaRetentionTransportResponse>(
      `/media/${encodeURIComponent(
        normalizedProvider
      )}/${encodeURIComponent(
        normalizedItemId
      )}/retention`,
      {
        method: "GET",
        signal
      }
    );

  const retention = mapMediaRetention(response);

  if (
    retention.provider !== normalizedProvider ||
    retention.itemId !== normalizedItemId
  ) {
    throw new Error(
      "Media retention response did not match the requested media identity."
    );
  }

  return retention;
}
