import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const can = vi.fn<(permission: string) => boolean>();

vi.mock("../../../lib/authorization", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../lib/authorization")>();

  return {
    ...actual,
    usePermission: () => ({
      grantedPermissionPatterns: [],
      deniedPermissionPatterns: [],
      can,
      canAny: () => false,
      canEvery: () => false
    })
  };
});

vi.mock("./LiveSessionManagement", () => ({
  LiveSessionManagement: () => <section data-testid="live-session-management">Live-session management</section>
}));

vi.mock("./RoleManagement", () => ({
  RoleManagement: () => <section data-testid="role-management">Role management</section>
}));

import { AdministrationView } from "./AdministrationView";

describe("AdministrationView", () => {
  beforeEach(() => {
    can.mockReset();
  });

  it("links supported administration surfaces allowed by effective permissions", () => {
    can.mockReturnValue(true);
    const markup = renderToStaticMarkup(<AdministrationView />);

    expect(markup).toContain("Management surfaces");
    expect(markup).toContain("Live-session management");
    expect(markup).toContain('href="/portal/users"');
    expect(markup).toContain('href="/portal/services"');
    expect(markup).toContain('href="/portal/administration/downloads"');
    expect(markup).toContain('href="/portal/requests"');
    expect(markup).toContain('href="/portal/media"');
    expect(markup).toContain('href="/portal/sports"');
  });

  it("hides destinations that the current user cannot read", () => {
    can.mockImplementation((permission) => permission === "system.health.read");
    const markup = renderToStaticMarkup(<AdministrationView />);

    expect(markup).toContain('href="/portal/services"');
    expect(markup).not.toContain('href="/portal/users"');
    expect(markup).not.toContain('href="/portal/administration/downloads"');
    expect(markup).not.toContain('href="/portal/requests"');
    expect(markup).not.toContain('href="/portal/media"');
    expect(markup).not.toContain('href="/portal/sports"');
  });
});
