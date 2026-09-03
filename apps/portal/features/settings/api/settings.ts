import type { AtlasCurrentUserResponse } from "../../../lib/api/contracts";
import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type SettingsProfile = AtlasCurrentUserResponse;

export type SettingsProfileUpdate = Readonly<{
  displayName: string;
  firstName: string;
  lastName: string;
  email: string;
  discordAccount: string;
  emailNotificationsEnabled: boolean;
  discordNotificationsEnabled: boolean;
}>;

function requiredString(value: string, label: string): string {
  const normalized = value.trim();

  if (!normalized) {
    throw new Error(`${label} cannot be empty.`);
  }

  return normalized;
}

function optionalString(value: string): string | null {
  const normalized = value.trim();
  return normalized || null;
}

export async function readSettingsProfile(): Promise<SettingsProfile> {
  return authenticatedAtlasApiRequest<SettingsProfile>("/auth/me", {
    method: "GET",
    cache: "no-store"
  });
}

export async function updateSettingsProfile(
  update: SettingsProfileUpdate
): Promise<SettingsProfile> {
  const displayName = requiredString(update.displayName, "Display name");
  const email = requiredString(update.email, "Email address");
  const discordAccount = optionalString(update.discordAccount);

  if (update.discordNotificationsEnabled && discordAccount === null) {
    throw new Error(
      "Add a Discord account before enabling Discord notifications."
    );
  }

  return authenticatedAtlasApiRequest<SettingsProfile>("/auth/me", {
    method: "PATCH",
    cache: "no-store",
    body: {
      display_name: displayName,
      first_name: optionalString(update.firstName),
      last_name: optionalString(update.lastName),
      email,
      discord_account: discordAccount,
      email_notifications_enabled: update.emailNotificationsEnabled,
      discord_notifications_enabled: update.discordNotificationsEnabled
    },
    retryPolicy: {
      maxRetries: 0,
      baseDelayMs: 250,
      maxDelayMs: 5_000
    }
  });
}
