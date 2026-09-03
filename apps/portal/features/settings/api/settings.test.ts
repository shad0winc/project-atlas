import {
  beforeEach,
  describe,
  expect,
  it,
  vi
} from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest:
    authenticatedAtlasApiRequestMock
}));

import {
  readSettingsProfile,
  updateSettingsProfile
} from "./settings";

const profile = {
  user_id: "usr_123",
  username: "michael",
  display_name: "Michael",
  first_name: "Michael",
  last_name: "Atlas",
  email: "michael@example.com",
  discord_account: null,
  email_notifications_enabled: false,
  discord_notifications_enabled: false,
  roles: ["member"],
  provider: "jellyfin",
  granted_permission_patterns: [
    "users.self.read",
    "users.self.update"
  ],
  denied_permission_patterns: []
};

beforeEach(() => {
  authenticatedAtlasApiRequestMock.mockReset();
});

describe("Settings API boundary", () => {
  it("reads the authenticated profile from auth/me", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValueOnce(
      profile
    );

    await expect(readSettingsProfile()).resolves.toEqual(
      profile
    );

    expect(
      authenticatedAtlasApiRequestMock
    ).toHaveBeenCalledWith("/auth/me", {
      method: "GET",
      cache: "no-store"
    });
  });

  it("updates only supported self-service profile fields", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValueOnce({
      ...profile,
      display_name: "Atlas User",
      discord_account: "atlas-user"
    });

    await updateSettingsProfile({
      displayName: "  Atlas User  ",
      firstName: " Michael ",
      lastName: " Atlas ",
      email: " michael@example.com ",
      discordAccount: " atlas-user ",
      emailNotificationsEnabled: true,
      discordNotificationsEnabled: true
    });

    expect(
      authenticatedAtlasApiRequestMock
    ).toHaveBeenCalledWith(
      "/auth/me",
      expect.objectContaining({
        method: "PATCH",
        cache: "no-store",
        body: {
          display_name: "Atlas User",
          first_name: "Michael",
          last_name: "Atlas",
          email: "michael@example.com",
          discord_account: "atlas-user",
          email_notifications_enabled: true,
          discord_notifications_enabled: true
        },
        retryPolicy: expect.objectContaining({
          maxRetries: 0
        })
      })
    );
  });

  it("rejects required blank fields before transport", async () => {
    await expect(
      updateSettingsProfile({
        displayName: "   ",
        firstName: "",
        lastName: "",
        email: "michael@example.com",
        discordAccount: "",
        emailNotificationsEnabled: false,
        discordNotificationsEnabled: false
      })
    ).rejects.toThrow("Display name cannot be empty.");

    expect(
      authenticatedAtlasApiRequestMock
    ).not.toHaveBeenCalled();
  });

  it("rejects Discord notifications without an account", async () => {
    await expect(
      updateSettingsProfile({
        displayName: "Michael",
        firstName: "",
        lastName: "",
        email: "michael@example.com",
        discordAccount: " ",
        emailNotificationsEnabled: false,
        discordNotificationsEnabled: true
      })
    ).rejects.toThrow(
      "Add a Discord account before enabling Discord notifications."
    );

    expect(
      authenticatedAtlasApiRequestMock
    ).not.toHaveBeenCalled();
  });
});
