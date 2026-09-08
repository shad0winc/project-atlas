import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import {
  createAdminSportsProviderAccount,
  loadAdminSportsProviders,
  loadAdminSportsResourcePool,
  removeAdminSportsProviderAccount,
  replaceAdminSportsAccountCredentials,
  testAdminSportsAccountConnection,
  updateAdminSportsAccount
} from "./provider-accounts";

function providerResponse(): unknown {
  return {
    providers: [
      {
        provider_id: "evestv",
        display_name: "EVESTV",
        account_count: 1,
        enabled_account_count: 0,
        configured_max_connections: 1,
        enabled_max_connections: 0,
        accounts: [
          {
            source_id: "evestv-account-1",
            display_name: "EVESTV",
            account_display_name: "EVESTV Account",
            enabled: false,
            kind: "licensed_subscription",
            trust_class: "trusted",
            priority: 100,
            max_connections: 1,
            expires_at: null,
            backend_configured: true
          }
        ]
      }
    ]
  };
}

describe("Sports provider administration API", () => {
  beforeEach(() => {
    authenticatedAtlasApiRequestMock.mockReset();
  });

  it("loads and maps the public provider inventory", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(providerResponse());

    await expect(loadAdminSportsProviders()).resolves.toEqual([
      {
        providerId: "evestv",
        displayName: "EVESTV",
        accountCount: 1,
        enabledAccountCount: 0,
        configuredMaxConnections: 1,
        enabledMaxConnections: 0,
        accounts: [
          {
            sourceId: "evestv-account-1",
            displayName: "EVESTV",
            accountDisplayName: "EVESTV Account",
            enabled: false,
            kind: "licensed_subscription",
            trustClass: "trusted",
            priority: 100,
            maxConnections: 1,
            expiresAt: null,
            backendConfigured: true
          }
        ]
      }
    ]);

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith("/admin/sports/providers", {
      method: "GET",
      cache: "no-store"
    });
  });

  it("rejects private backend metadata at the Portal boundary", async () => {
    const unsafe = providerResponse() as {
      providers: Array<{
        accounts: Array<Record<string, unknown>>;
      }>;
    };

    unsafe.providers[0].accounts[0].backend_reference = "dispatcharr:m3u:private";

    authenticatedAtlasApiRequestMock.mockResolvedValue(unsafe);

    await expect(loadAdminSportsProviders()).rejects.toThrow(
      "Private provider field crossed the Portal boundary"
    );
  });

  it("loads resource-pool utilization", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      total_capacity: 3,
      active: 1,
      available: 2,
      accounts: [
        {
          source_id: "provider-account-1",
          enabled: true,
          capacity: 3,
          active: 1,
          available: 2
        }
      ]
    });

    await expect(loadAdminSportsResourcePool()).resolves.toEqual({
      totalCapacity: 3,
      active: 1,
      available: 2,
      accounts: [
        {
          sourceId: "provider-account-1",
          enabled: true,
          capacity: 3,
          active: 1,
          available: 2
        }
      ]
    });
  });

  it("updates only supported safe account metadata", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(providerResponse());

    await updateAdminSportsAccount("provider a", "source one", {
      accountDisplayName: "Primary",
      enabled: true,
      maxConnections: 4
    });

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/admin/sports/providers/provider%20a/accounts/source%20one",
      {
        method: "PATCH",
        cache: "no-store",
        body: {
          account_display_name: "Primary",
          enabled: true,
          max_connections: 4
        }
      }
    );
  });

  it("tests a provider connection without credentials", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      ok: true,
      status: "Active",
      expires_at: null,
      provider_max_connections: 2,
      active_connections: 0
    });

    await expect(testAdminSportsAccountConnection("provider-a", "source-a")).resolves.toEqual({
      ok: true,
      status: "Active",
      expiresAt: null,
      providerMaxConnections: 2,
      activeConnections: 0
    });

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/admin/sports/providers/provider-a/accounts/source-a/test-connection",
      {
        method: "POST",
        cache: "no-store"
      }
    );
  });

  it("sends replacement credentials only in the request body", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      account_id: 7,
      name: "Provider Account",
      account_type: "XC",
      enabled: false,
      configured_max_connections: 1,
      credentials_configured: true
    });

    await replaceAdminSportsAccountCredentials("provider-a", "source-a", {
      serverUrl: "https://provider.invalid",
      username: "replacement-user",
      password: "replacement-secret"
    });

    const [path, options] = authenticatedAtlasApiRequestMock.mock.calls[0] ?? [];

    expect(path).toBe("/admin/sports/providers/provider-a/accounts/source-a/credentials");

    expect(String(path)).not.toContain("replacement-user");
    expect(String(path)).not.toContain("replacement-secret");

    expect(options).toEqual({
      method: "PATCH",
      cache: "no-store",
      body: {
        server_url: "https://provider.invalid",
        username: "replacement-user",
        password: "replacement-secret"
      }
    });
  });

  it("creates a disabled account through the public lifecycle endpoint", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue(providerResponse());

    await createAdminSportsProviderAccount("xc4", {
      sourceId: "xc4-primary",
      providerDisplayName: "XC4",
      accountDisplayName: "XC4 Primary",
      serverUrl: "https://provider.invalid",
      username: "provider-user",
      password: "provider-secret",
      maxConnections: 2,
      priority: 120
    });

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/admin/sports/providers/xc4/accounts",
      {
        method: "POST",
        cache: "no-store",
        body: {
          source_id: "xc4-primary",
          provider_display_name: "XC4",
          account_display_name: "XC4 Primary",
          server_url: "https://provider.invalid",
          username: "provider-user",
          password: "provider-secret",
          max_connections: 2,
          priority: 120
        }
      }
    );
  });

  it("requires a confirmed, correctly scoped removal", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      removed: true,
      source_id: "source-a"
    });

    await expect(removeAdminSportsProviderAccount("provider-a", "source-a")).resolves.toBe(true);

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/admin/sports/providers/provider-a/accounts/source-a",
      {
        method: "DELETE",
        cache: "no-store"
      }
    );
  });
});
