import { describe, expect, it } from "vitest";
import type { AdminInvitation } from "../api/admin-identity";
import {
  INVITATION_ARCHIVE_DELAY_MS,
  isArchivedInvitation,
  partitionInvitations
} from "./invitation-archive";

const now = Date.parse("2026-11-07T12:00:00Z");
const base: AdminInvitation = {
  inviteId: "example",
  email: "friend@example.invalid",
  role: "member",
  status: "pending",
  createdAt: "2026-01-01T00:00:00Z",
  expiresAt: "2026-12-01T00:00:00Z"
};

describe("invitation archive", () => {
  it.each(["completed", "revoked"])(
    "archives %s at exactly 24 hours after that action",
    (status) => {
      const timestamp = new Date(now - INVITATION_ARCHIVE_DELAY_MS).toISOString();
      const invitation = { ...base, status, completedAt: timestamp, revokedAt: timestamp };
      expect(isArchivedInvitation(invitation, now - 1)).toBe(false);
      expect(isArchivedInvitation(invitation, now)).toBe(true);
      expect(isArchivedInvitation(invitation, now + 1)).toBe(true);
    }
  );

  it("uses the status-specific timestamp rather than creation or a different action", () => {
    expect(
      isArchivedInvitation(
        {
          ...base,
          status: "completed",
          completedAt: new Date(now - 1000).toISOString(),
          revokedAt: "2020-01-01T00:00:00Z"
        },
        now
      )
    ).toBe(false);
    expect(
      isArchivedInvitation(
        { ...base, status: "revoked", revokedAt: new Date(now + 1000).toISOString() },
        now
      )
    ).toBe(false);
    expect(isArchivedInvitation({ ...base, completedAt: "2020-01-01T00:00:00Z" }, now)).toBe(false);
  });

  it("retains records with missing or malformed lifecycle timestamps in Current", () => {
    for (const timestamp of [null, undefined, "invalid"]) {
      expect(isArchivedInvitation({ ...base, status: "revoked", revokedAt: timestamp }, now)).toBe(
        false
      );
    }
  });

  it("preserves every record and partitions old history without mutating status", () => {
    const records = [
      base,
      { ...base, inviteId: "revoked", status: "revoked", revokedAt: "2020-01-01T00:00:00Z" },
      { ...base, inviteId: "accepted", status: "completed", completedAt: "2020-01-01T00:00:00Z" }
    ];
    const snapshot = JSON.stringify(records);
    const result = partitionInvitations(records, now);
    expect(result.current.map((item) => item.inviteId)).toEqual(["example"]);
    expect(result.archived.map((item) => item.inviteId)).toEqual(["revoked", "accepted"]);
    expect(JSON.stringify(records)).toBe(snapshot);
  });
});
