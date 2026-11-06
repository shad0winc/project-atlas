import type { AdminInvitation } from "../api/admin-identity";

export const INVITATION_ARCHIVE_DELAY_MS = 24 * 60 * 60 * 1000;

export function isArchivedInvitation(invitation: AdminInvitation, now: number): boolean {
  const terminalAt =
    invitation.status === "completed"
      ? invitation.completedAt
      : invitation.status === "revoked"
        ? invitation.revokedAt
        : null;
  if (!terminalAt) return false;
  const timestamp = Date.parse(terminalAt);
  return Number.isFinite(timestamp) && timestamp + INVITATION_ARCHIVE_DELAY_MS <= now;
}

export function partitionInvitations(invitations: readonly AdminInvitation[], now: number) {
  const current: AdminInvitation[] = [];
  const archived: AdminInvitation[] = [];
  for (const invitation of invitations) {
    (isArchivedInvitation(invitation, now) ? archived : current).push(invitation);
  }
  return { current, archived };
}
