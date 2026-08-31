import { describe, expect, it } from "vitest";

import { ATLAS_PERMISSIONS } from "./permissions";

describe("Sports recording permissions", () => {
  it("uses a dedicated recording-management permission", () => {
    expect(
      ATLAS_PERMISSIONS.sportsRecordingsManage
    ).toBe("sports.recordings.manage");
  });
});
