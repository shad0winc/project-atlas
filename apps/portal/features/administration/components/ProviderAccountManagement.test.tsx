import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  can: vi.fn(),
  useAdminSportsProviders: vi.fn()
}));

vi.mock("../../../lib/authorization", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../lib/authorization")>();

  return {
    ...actual,
    usePermission: () => ({
      grantedPermissionPatterns: [],
      deniedPermissionPatterns: [],
      can: mocks.can,
      canAny: () => false,
      canEvery: () => false
    })
  };
});

vi.mock("../hooks/use-admin-sports-providers", () => ({
  useAdminSportsProviders: mocks.useAdminSportsProviders
}));

import { ProviderAccountManagement } from "./ProviderAccountManagement";

function readyHook() {
  return {
    state: {
      status: "ready",
      providers: [
        {
          providerId: "xc-provider-2",
          displayName: "line",
          accountCount: 1,
          enabledAccountCount: 0,
          configuredMaxConnections: 1,
          enabledMaxConnections: 0,
          accounts: [
            {
              sourceId: "xc-account-2",
              displayName: "line",
              accountDisplayName: "XC Account 2",
              enabled: false,
              kind: "licensed_subscription",
              trustClass: "trusted",
              priority: 110,
              maxConnections: 1,
              expiresAt: null,
              backendConfigured: true
            }
          ]
        }
      ],
      resourcePool: {
        totalCapacity: 0,
        active: 0,
        available: 0,
        accounts: [
          {
            sourceId: "xc-account-2",
            enabled: false,
            capacity: 0,
            active: 0,
            available: 0
          }
        ]
      }
    },
    refresh: vi.fn(),
    mutationError: null,
    busyKey: null,
    connections: {
      "xc-account-2": {
        accountId: 2,
        name: "Provider Account",
        accountType: "XC",
        enabled: false,
        configuredMaxConnections: 1,
        credentialsConfigured: true
      }
    },
    connectionTests: {},
    renameProvider: vi.fn(),
    updateAccount: vi.fn(),
    setAccountEnabled: vi.fn(),
    loadConnection: vi.fn(),
    testConnection: vi.fn(),
    replaceCredentials: vi.fn(),
    createAccount: vi.fn(),
    removeAccount: vi.fn()
  };
}

describe("ProviderAccountManagement", () => {
  beforeEach(() => {
    mocks.can.mockReset();
    mocks.useAdminSportsProviders.mockReset();
    mocks.useAdminSportsProviders.mockReturnValue(readyHook());
  });

  it("is hidden without the dedicated management permission", () => {
    mocks.can.mockReturnValue(false);

    expect(renderToStaticMarkup(<ProviderAccountManagement />)).toBe("");

    expect(mocks.useAdminSportsProviders).toHaveBeenCalledWith(false);
  });

  it("renders safe provider management without stored secrets", () => {
    mocks.can.mockImplementation((permission) => permission === "sports.providers.manage");

    const markup = renderToStaticMarkup(<ProviderAccountManagement />);

    expect(markup).toContain("Sports provider accounts");
    expect(markup).toContain("xc-provider-2");
    expect(markup).toContain("xc-account-2");
    expect(markup).toContain("XC Account 2");
    expect(markup).toContain("Priority: 110");
    expect(markup).toContain("(read-only)");
    expect(markup).toContain("Backend configured:");
    expect(markup).toContain("Enable pool participation");
    expect(markup).toContain("Test connection");
    expect(markup).toContain("Replace connection");
    expect(markup).toContain("Add provider account");
    expect(markup).toContain('type="password"');

    for (const forbidden of [
      "backend_reference",
      "dispatcharr:m3u:",
      "provider-secret",
      "replacement-secret",
      "https://provider."
    ]) {
      expect(markup.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }
  });
});
