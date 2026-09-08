import { describe, expect, it } from "vitest";

import { ATLAS_PERMISSIONS } from "./permissions";

describe("Sports provider administration permission", () => {
  it("matches the API authorization contract", () => {
    expect(ATLAS_PERMISSIONS.sportsProvidersManage).toBe("sports.providers.manage");
  });
});
