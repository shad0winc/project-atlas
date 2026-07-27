import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const can = vi.fn<(permission: string) => boolean>();

vi.mock("../../lib/authorization", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/authorization")>();

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

import { PortalAccessDenied } from "./PortalAccessDenied";
import { PortalPage } from "./PortalPage";

describe("PortalAccessDenied", () => {
  it("renders the standard accessible denied presentation", () => {
    const markup = renderToStaticMarkup(<PortalAccessDenied />);

    expect(markup).toContain('role="status"');
    expect(markup).toContain('id="portal-access-denied-title"');
    expect(markup).toContain("Access unavailable");
    expect(markup).toContain("Your Atlas account does not have permission to access this section.");
    expect(markup).toContain("contact your Atlas administrator");
  });

  it("supports contextual denied copy", () => {
    const markup = renderToStaticMarkup(
      <PortalAccessDenied
        description="Dashboard access is not available."
        guidance="Ask an owner to review your account."
        title="Dashboard unavailable"
      />
    );

    expect(markup).toContain("Dashboard unavailable");
    expect(markup).toContain("Dashboard access is not available.");
    expect(markup).toContain("Ask an owner to review your account.");
  });
});

describe("PortalPage", () => {
  beforeEach(() => {
    can.mockReset();
  });

  it("renders the canonical page frame when permission is granted", () => {
    can.mockReturnValue(true);

    const markup = renderToStaticMarkup(
      <PortalPage
        actions={<button type="button">Refresh</button>}
        description="Review Atlas operations."
        eyebrow="Dashboard"
        permission="atlas.dashboard.read"
        title="System overview"
      >
        <div>Protected dashboard content</div>
      </PortalPage>
    );

    expect(can).toHaveBeenCalledWith("atlas.dashboard.read");
    expect(markup).toContain('class="portal-page"');
    expect(markup).toContain('class="portal-page-header"');
    expect(markup).toContain("Dashboard");
    expect(markup).toContain("System overview");
    expect(markup).toContain("Review Atlas operations.");
    expect(markup).toContain("Refresh");
    expect(markup).toContain("Protected dashboard content");
    expect(markup).not.toContain("Access unavailable");
  });

  it("renders the standard denied boundary instead of protected children", () => {
    can.mockReturnValue(false);

    const markup = renderToStaticMarkup(
      <PortalPage
        accessDeniedDescription="Dashboard access is not available."
        eyebrow="Dashboard"
        permission="atlas.dashboard.read"
        title="System overview"
      >
        <div>Protected dashboard content</div>
      </PortalPage>
    );

    expect(can).toHaveBeenCalledWith("atlas.dashboard.read");
    expect(markup).toContain("Access unavailable");
    expect(markup).toContain("Dashboard access is not available.");
    expect(markup).not.toContain("Protected dashboard content");
  });

  it("omits optional description and actions when they are not supplied", () => {
    can.mockReturnValue(true);

    const markup = renderToStaticMarkup(
      <PortalPage eyebrow="Media" permission="media.read" title="Media library">
        <div>Media content</div>
      </PortalPage>
    );

    expect(markup).not.toContain('class="portal-page-actions"');
    expect(markup).toContain("Media library");
    expect(markup).toContain("Media content");
  });
});
