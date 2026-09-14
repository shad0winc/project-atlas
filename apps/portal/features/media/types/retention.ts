export type MediaRetentionLifecycleState =
  | "protected"
  | "scheduled"
  | "eligible"
  | "unknown";

export type MediaRetentionLifecycleRule =
  | "policy_protected"
  | "disliked_24h"
  | "watched_72h"
  | "unwatched_30d"
  | "legacy"
  | "unavailable";

export type MediaRetentionLifecycle = Readonly<{
  state: MediaRetentionLifecycleState;
  rule: MediaRetentionLifecycleRule;
  basisAt: string | null;
  deleteAt: string | null;
}>;

export type MediaRetention = Readonly<{
  provider: string;
  itemId: string;
  eligible: boolean;
  retained: boolean;
  lifecycle: MediaRetentionLifecycle;
}>;

const LIFECYCLE_STATES = new Set<MediaRetentionLifecycleState>([
  "protected",
  "scheduled",
  "eligible",
  "unknown"
]);

const LIFECYCLE_RULES = new Set<MediaRetentionLifecycleRule>([
  "policy_protected",
  "disliked_24h",
  "watched_72h",
  "unwatched_30d",
  "legacy",
  "unavailable"
]);

function normalizeRequiredText(
  value: string,
  field: string
): string {
  const normalized = value.trim();

  if (normalized.length === 0) {
    throw new Error(`${field} must not be empty.`);
  }

  return normalized;
}

function normalizeTimestamp(
  value: string | null,
  field: string
): string | null {
  if (value === null) {
    return null;
  }

  const normalized = value.trim();

  if (
    normalized.length === 0 ||
    Number.isNaN(Date.parse(normalized))
  ) {
    throw new Error(`${field} must be a valid timestamp.`);
  }

  return normalized;
}

function createMediaRetentionLifecycle(
  lifecycle: MediaRetentionLifecycle
): MediaRetentionLifecycle {
  if (!LIFECYCLE_STATES.has(lifecycle.state)) {
    throw new Error("retention.lifecycle.state is invalid.");
  }

  if (!LIFECYCLE_RULES.has(lifecycle.rule)) {
    throw new Error("retention.lifecycle.rule is invalid.");
  }

  const basisAt = normalizeTimestamp(
    lifecycle.basisAt,
    "retention.lifecycle.basisAt"
  );

  const deleteAt = normalizeTimestamp(
    lifecycle.deleteAt,
    "retention.lifecycle.deleteAt"
  );

  if (
    lifecycle.state === "scheduled" &&
    deleteAt === null
  ) {
    throw new Error(
      "Scheduled retention lifecycle requires deleteAt."
    );
  }

  if (
    lifecycle.state === "protected" &&
    (basisAt !== null || deleteAt !== null)
  ) {
    throw new Error(
      "Protected retention lifecycle must not carry deletion timing."
    );
  }

  if (
    lifecycle.state === "unknown" &&
    lifecycle.rule === "unavailable" &&
    deleteAt !== null
  ) {
    throw new Error(
      "Unavailable retention lifecycle must not carry deleteAt."
    );
  }

  return Object.freeze({
    state: lifecycle.state,
    rule: lifecycle.rule,
    basisAt,
    deleteAt
  });
}

export function createMediaRetention(
  retention: MediaRetention
): MediaRetention {
  const provider = normalizeRequiredText(
    retention.provider,
    "retention.provider"
  ).toLowerCase();

  const itemId = normalizeRequiredText(
    retention.itemId,
    "retention.itemId"
  );

  if (retention.eligible && retention.retained) {
    throw new Error(
      "retention.eligible and retention.retained conflict."
    );
  }

  if (!retention.eligible && !retention.retained) {
    throw new Error(
      "retention.eligible and retention.retained conflict."
    );
  }

  const lifecycle = createMediaRetentionLifecycle(
    retention.lifecycle
  );

  if (
    lifecycle.state === "eligible" &&
    !retention.eligible
  ) {
    throw new Error(
      "Eligible retention lifecycle requires eligible=true."
    );
  }

  const isLegacyEligibility =
    lifecycle.state === "unknown" &&
    lifecycle.rule === "legacy";

  if (
    lifecycle.state !== "eligible" &&
    retention.eligible &&
    !isLegacyEligibility
  ) {
    throw new Error(
      "Non-eligible retention lifecycle requires eligible=false."
    );
  }

  return Object.freeze({
    provider,
    itemId,
    eligible: retention.eligible,
    retained: retention.retained,
    lifecycle
  });
}
