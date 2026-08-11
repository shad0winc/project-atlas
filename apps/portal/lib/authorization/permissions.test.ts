import { describe, expect, it } from "vitest";

import {
  ATLAS_PERMISSIONS,
  atlasPermissionPatternMatches,
  hasAnyAtlasPermission,
  hasAtlasPermission,
  hasEveryAtlasPermission,
  normalizeAtlasPermission,
  type AtlasEffectivePermissionPatterns
} from "./permissions";

function authorization(
  grantedPermissionPatterns: readonly string[],
  deniedPermissionPatterns: readonly string[] = []
): AtlasEffectivePermissionPatterns {
  return {
    grantedPermissionPatterns,
    deniedPermissionPatterns
  };
}

describe("Atlas Portal effective permission evaluation", () => {
  it("publishes stable Request permission identifiers", () => {
    expect(ATLAS_PERMISSIONS.requestsRead).toBe("requests.read");
    expect(ATLAS_PERMISSIONS.requestsCreate).toBe("requests.create");
    expect(ATLAS_PERMISSIONS.requestsCancel).toBe("requests.cancel");
  });

  it("normalizes permission names", () => {
    expect(normalizeAtlasPermission(" MEDIA.READ ")).toBe("media.read");
  });

  it("rejects empty permission names", () => {
    expect(() => normalizeAtlasPermission("  ")).toThrow("Atlas permission cannot be empty.");
  });

  it("matches exact permissions", () => {
    expect(atlasPermissionPatternMatches("media.read", "media.read")).toBe(true);
    expect(atlasPermissionPatternMatches("media.read", "media.write")).toBe(false);
  });

  it("matches the global wildcard", () => {
    expect(atlasPermissionPatternMatches("*", "atlas.dashboard.read")).toBe(true);
  });

  it("matches namespace wildcards across nested components", () => {
    expect(atlasPermissionPatternMatches("atlas.*", "atlas.dashboard.read")).toBe(true);
    expect(atlasPermissionPatternMatches("users.*", "users.self.update")).toBe(true);
  });

  it("matches action wildcards across namespaces", () => {
    expect(atlasPermissionPatternMatches("*.read", "atlas.dashboard.read")).toBe(true);
    expect(atlasPermissionPatternMatches("*.read", "users.self.read")).toBe(true);
    expect(atlasPermissionPatternMatches("*.read", "media.write")).toBe(false);
  });

  it("does not cross unrelated namespaces", () => {
    expect(atlasPermissionPatternMatches("media.*", "atlas.dashboard.read")).toBe(false);
  });

  it("allows an exact effective grant", () => {
    expect(hasAtlasPermission(authorization(["media.read"]), "media.read")).toBe(true);
  });

  it("allows a wildcard effective grant", () => {
    expect(hasAtlasPermission(authorization(["atlas.*"]), "atlas.dashboard.read")).toBe(true);
  });

  it("denies a permission without a matching grant", () => {
    expect(hasAtlasPermission(authorization(["media.read"]), "users.read")).toBe(false);
  });

  it("applies an exact denial before a wildcard grant", () => {
    expect(hasAtlasPermission(authorization(["users.*"], ["users.delete"]), "users.delete")).toBe(
      false
    );
  });

  it("applies a wildcard denial before an exact grant", () => {
    expect(
      hasAtlasPermission(authorization(["users.self.read"], ["users.*"]), "users.self.read")
    ).toBe(false);
  });

  it("supports direct grants independently from roles", () => {
    expect(hasAtlasPermission(authorization(["system.health.read"]), "system.health.read")).toBe(
      true
    );
  });

  it("supports any and every checks", () => {
    const effective = authorization(["media.read", "requests.read", "users.self.read"]);

    expect(hasAnyAtlasPermission(effective, ["users.delete", "requests.read"])).toBe(true);

    expect(hasEveryAtlasPermission(effective, ["media.read", "users.self.read"])).toBe(true);

    expect(hasEveryAtlasPermission(effective, ["media.read", "users.delete"])).toBe(false);
  });

  it("denies access when effective patterns are empty", () => {
    expect(hasAtlasPermission(authorization([]), "media.read")).toBe(false);
  });
});
