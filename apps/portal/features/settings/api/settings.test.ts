import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { readSettingsProfile, updateSettingsDisplayName } from "./settings";

const profile = {
  user_id: "usr_123",
  username: "michael",
  display_name: "Michael",
  roles: ["member"],
  provider: "jellyfin",
  granted_permission_patterns: ["users.self.read", "users.self.update"],
  denied_permission_patterns: []
};

beforeEach(() => {
  authenticatedAtlasApiRequestMock.mockReset();
});

describe("Settings API boundary", () => {
  it("reads the authenticated profile from auth/me", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValueOnce(profile);

    await expect(readSettingsProfile()).resolves.toEqual(profile);
    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith("/auth/me", {
      method: "GET",
      cache: "no-store"
    });
  });

  it("updates only display_name and disables mutation retries", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValueOnce({
      ...profile,
      display_name: "Atlas User"
    });

    await updateSettingsDisplayName("  Atlas User  ");

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/auth/me",
      expect.objectContaining({
        method: "PATCH",
        cache: "no-store",
        body: {
          display_name: "Atlas User"
        },
        retryPolicy: expect.objectContaining({
          maxRetries: 0
        })
      })
    );
  });

  it("rejects a blank display name before transport", async () => {
    await expect(updateSettingsDisplayName("   ")).rejects.toThrow("Display name cannot be empty.");
    expect(authenticatedAtlasApiRequestMock).not.toHaveBeenCalled();
  });
});
