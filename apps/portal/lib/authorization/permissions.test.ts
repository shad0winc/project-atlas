import { describe, expect, it } from "vitest";

import {
  atlasPermissionPatternMatches,
  atlasRolePermissions,
  hasAnyAtlasPermission,
  hasAtlasPermission,
  hasEveryAtlasPermission,
  normalizeAtlasPermission,
  normalizeAtlasRole
} from "./permissions";

describe("Atlas Portal permission evaluation", () => {
  it("normalizes role names and legacy aliases", () => {
    expect(normalizeAtlasRole(" GLOBAL_ADMIN ")).toBe("global_admin");
    expect(normalizeAtlasRole("admin")).toBe("global_admin");
    expect(normalizeAtlasRole("user")).toBe("member");
    expect(normalizeAtlasRole("games_admin")).toBe("gameserver_admin");
    expect(normalizeAtlasRole("readonly")).toBe("read_only");
  });

  it("normalizes permission names", () => {
    expect(normalizeAtlasPermission(" MEDIA.READ ")).toBe("media.read");
  });

  it("rejects empty normalized values", () => {
    expect(() => normalizeAtlasRole("  ")).toThrow("Atlas role cannot be empty.");
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

  it("resolves owner access through the global wildcard", () => {
    expect(hasAtlasPermission(["owner"], "users.delete")).toBe(true);
  });

  it("resolves global administrator nested permissions", () => {
    expect(hasAtlasPermission(["global_admin"], "atlas.dashboard.read")).toBe(true);
    expect(hasAtlasPermission(["global_admin"], "system.health.read")).toBe(true);
    expect(hasAtlasPermission(["global_admin"], "users.self.update")).toBe(true);
  });

  it("resolves read-only permissions through the action wildcard", () => {
    expect(hasAtlasPermission(["read_only"], "atlas.dashboard.read")).toBe(true);
    expect(hasAtlasPermission(["read_only"], "users.self.read")).toBe(true);
    expect(hasAtlasPermission(["read_only"], "users.self.update")).toBe(false);
  });

  it("resolves member permissions without administrative access", () => {
    expect(hasAtlasPermission(["member"], "atlas.dashboard.read")).toBe(true);
    expect(hasAtlasPermission(["member"], "media.read")).toBe(true);
    expect(hasAtlasPermission(["member"], "users.read")).toBe(false);
  });

  it("merges permissions from multiple roles", () => {
    expect(
      hasEveryAtlasPermission(["member", "monitoring_admin"], ["media.read", "system.health.read"])
    ).toBe(true);
  });

  it("supports any/every checks and unknown roles", () => {
    expect(hasAnyAtlasPermission(["member"], ["users.delete", "requests.read"])).toBe(true);

    expect(hasEveryAtlasPermission(["member"], ["requests.read", "users.delete"])).toBe(false);

    expect(atlasRolePermissions("unknown_role")).toEqual([]);

    expect(hasAtlasPermission(["unknown_role"], "media.read")).toBe(false);
  });
});
