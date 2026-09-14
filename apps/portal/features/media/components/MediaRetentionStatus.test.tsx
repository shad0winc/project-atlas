import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { MediaRetention } from "../types/retention";
import { MediaRetentionStatus } from "./MediaRetentionStatus";

function retention(
  overrides: Partial<MediaRetention> = {}
): MediaRetention {
  return {
    provider: "jellyfin",
    itemId: "jf-interstellar",
    eligible: false,
    retained: true,
    lifecycle: {
      state: "scheduled",
      rule: "unwatched_30d",
      basisAt: "2026-08-15T12:00:00Z",
      deleteAt: "2026-09-14T12:00:00Z"
    },
    ...overrides
  };
}

describe("MediaRetentionStatus", () => {
  it("renders the authoritative scheduled deletion timestamp", () => {
    const markup = renderToStaticMarkup(
      <MediaRetentionStatus retention={retention()} />
    );

    expect(markup).toContain("Scheduled for deletion");
    expect(markup).toContain("2026-09-14T12:00:00Z");
    expect(markup).toContain('dateTime="2026-09-14T12:00:00Z"');
  });

  it("renders Favorite protection without inventing a deadline", () => {
    const markup = renderToStaticMarkup(
      <MediaRetentionStatus
        retention={retention({
          lifecycle: {
            state: "protected",
            rule: "policy_protected",
            basisAt: null,
            deleteAt: null
          }
        })}
      />
    );

    expect(markup).toContain("Protected from automatic deletion");
    expect(markup).not.toContain("Scheduled for deletion");
  });

  it("renders an eligible disliked item using authoritative state", () => {
    const markup = renderToStaticMarkup(
      <MediaRetentionStatus
        retention={retention({
          eligible: true,
          retained: false,
          lifecycle: {
            state: "eligible",
            rule: "disliked_24h",
            basisAt: "2026-09-13T12:00:00Z",
            deleteAt: "2026-09-14T12:00:00Z"
          }
        })}
      />
    );

    expect(markup).toContain("Eligible for deletion");
    expect(markup).toContain("2026-09-14T12:00:00Z");
  });

  it("fails closed in presentation for unavailable lifecycle state", () => {
    const markup = renderToStaticMarkup(
      <MediaRetentionStatus
        retention={retention({
          lifecycle: {
            state: "unknown",
            rule: "unavailable",
            basisAt: null,
            deleteAt: null
          }
        })}
      />
    );

    expect(markup).toContain("Deletion schedule unavailable");
    expect(markup).not.toContain("Scheduled for deletion");
  });

  it("does not calculate or fabricate a different deletion timestamp", () => {
    const authoritativeDeleteAt =
      "2031-02-03T04:05:06Z";

    const markup = renderToStaticMarkup(
      <MediaRetentionStatus
        retention={retention({
          lifecycle: {
            state: "scheduled",
            rule: "watched_72h",
            basisAt: "2030-01-01T00:00:00Z",
            deleteAt: authoritativeDeleteAt
          }
        })}
      />
    );

    expect(markup).toContain(authoritativeDeleteAt);
  });
});
