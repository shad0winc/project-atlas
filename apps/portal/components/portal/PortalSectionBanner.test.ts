import { describe, expect, it } from "vitest";

import { portalBannerForPathname } from "./PortalSectionBanner";

describe("portalBannerForPathname", () => {
  it.each([
    ["/portal", "Portal_Home"],
    ["/portal/", "Portal_Home"],
    ["/portal/media", "Media_Library"],
    ["/portal/library", "Media_Library"],
    ["/portal/theater", "Theater_Playback"],
    ["/portal/sports", "Sports"],
    ["/portal/requests", "Requests"],
    ["/portal/favorites", "Favorites"],
    ["/portal/downloads", "Downloads_Automation"],
    ["/portal/administration/downloads", "Downloads_Automation"],
    ["/portal/users", "User_Identity"],
    ["/portal/administration", "Admin_Operations"],
  ])("maps %s to %s", (pathname, expected) => {
    expect(portalBannerForPathname(pathname)).toBe(expected);
  });

  it("maps nested supported routes to their owning section", () => {
    expect(portalBannerForPathname("/portal/media/example")).toBe(
      "Media_Library"
    );
    expect(portalBannerForPathname("/portal/users/example")).toBe(
      "User_Identity"
    );
    expect(
      portalBannerForPathname("/portal/administration/example")
    ).toBe("Admin_Operations");
  });

  it("does not invent a standalone Dislikes section route", () => {
    expect(portalBannerForPathname("/portal/dislikes")).toBeNull();
  });

  it("does not render a banner when pathname is unavailable", () => {
    expect(portalBannerForPathname(null)).toBeNull();
  });

  it("does not render a banner for unrelated routes", () => {
    expect(portalBannerForPathname("/portal/services")).toBeNull();
    expect(portalBannerForPathname("/login")).toBeNull();
  });
});
