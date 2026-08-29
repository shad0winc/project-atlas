import type { AtlasCurrentUserResponse } from "../../../lib/api/contracts";
import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type SettingsProfile = AtlasCurrentUserResponse;

export async function readSettingsProfile(): Promise<SettingsProfile> {
  return authenticatedAtlasApiRequest<SettingsProfile>("/auth/me", {
    method: "GET",
    cache: "no-store"
  });
}

export async function updateSettingsDisplayName(displayName: string): Promise<SettingsProfile> {
  const normalizedDisplayName = displayName.trim();

  if (!normalizedDisplayName) {
    throw new Error("Display name cannot be empty.");
  }

  return authenticatedAtlasApiRequest<SettingsProfile>("/auth/me", {
    method: "PATCH",
    cache: "no-store",
    body: {
      display_name: normalizedDisplayName
    },
    retryPolicy: {
      maxRetries: 0,
      baseDelayMs: 250,
      maxDelayMs: 5_000
    }
  });
}
