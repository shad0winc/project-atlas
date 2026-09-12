"use client";

import { usePathname } from "next/navigation";

export type PortalBannerStem =
  | "Portal_Home"
  | "Media_Library"
  | "Theater_Playback"
  | "Sports"
  | "Requests"
  | "Favorites"
  | "Admin_Operations"
  | "Downloads_Automation"
  | "User_Identity";

export function portalBannerForPathname(
  pathname: string | null
): PortalBannerStem | null {
  if (!pathname) {
    return null;
  }

  if (pathname === "/portal" || pathname === "/portal/") {
    return "Portal_Home";
  }

  if (
    pathname === "/portal/media" ||
    pathname.startsWith("/portal/media/") ||
    pathname === "/portal/library" ||
    pathname.startsWith("/portal/library/")
  ) {
    return "Media_Library";
  }

  if (
    pathname === "/portal/theater" ||
    pathname.startsWith("/portal/theater/")
  ) {
    return "Theater_Playback";
  }

  if (
    pathname === "/portal/sports" ||
    pathname.startsWith("/portal/sports/")
  ) {
    return "Sports";
  }

  if (
    pathname === "/portal/requests" ||
    pathname.startsWith("/portal/requests/")
  ) {
    return "Requests";
  }

  if (
    pathname === "/portal/favorites" ||
    pathname.startsWith("/portal/favorites/")
  ) {
    return "Favorites";
  }

  if (
    pathname === "/portal/downloads" ||
    pathname.startsWith("/portal/downloads/") ||
    pathname === "/portal/administration/downloads" ||
    pathname.startsWith("/portal/administration/downloads/")
  ) {
    return "Downloads_Automation";
  }

  if (
    pathname === "/portal/users" ||
    pathname.startsWith("/portal/users/")
  ) {
    return "User_Identity";
  }

  if (
    pathname === "/portal/administration" ||
    pathname.startsWith("/portal/administration/")
  ) {
    return "Admin_Operations";
  }

  return null;
}

function bannerPath(
  stem: PortalBannerStem,
  device: "Desktop" | "Tablet" | "Phone"
): string {
  return `/banners/${device}/${stem}_${device}_Banner.png`;
}

export function PortalSectionBanner(): React.ReactElement | null {
  const pathname = usePathname();
  const stem = portalBannerForPathname(pathname);

  if (stem === null) {
    return null;
  }

  return (
    <picture className="portal-section-banner">
      <source
        media="(max-width: 640px) and (orientation: portrait)"
        srcSet={bannerPath(stem, "Phone")}
      />
      <source
        media="(max-width: 1024px)"
        srcSet={bannerPath(stem, "Tablet")}
      />
      <img
        alt=""
        className="portal-section-banner-image"
        decoding="async"
        loading="eager"
        src={bannerPath(stem, "Desktop")}
      />
    </picture>
  );
}
