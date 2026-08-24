import { describe, expect, it } from "vitest";

import { ATLAS_PERMISSIONS } from "./permissions";

describe("Sports Portal permissions", () => {
  it("uses the frozen Sports read permission", () => {
    expect(ATLAS_PERMISSIONS.sportsRead).toBe("sports.read");
  });

  it("uses the frozen event-request permission", () => {
    expect(ATLAS_PERMISSIONS.sportsEventsRequest).toBe("sports.events.request");
  });
});
