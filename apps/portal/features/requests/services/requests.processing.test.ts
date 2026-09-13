import {
  beforeEach,
  describe,
  expect,
  it,
  vi
} from "vitest";

const {
  authenticatedAtlasApiRequestMock
} = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock(
  "../../../lib/services/authenticated",
  () => ({
    authenticatedAtlasApiRequest:
      authenticatedAtlasApiRequestMock
  })
);

import {
  readRequests
} from "./requests";

const REQUEST_ID = "req_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

beforeEach(() => {
  authenticatedAtlasApiRequestMock.mockReset();
});

describe("Request processing transport mapping", () => {
  it("preserves processing returned by the Atlas API", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({
      requests: [
        {
          request_id: REQUEST_ID,
          user_id: USER_ID,
          media_type: "movie",
          provider: "jellyseerr",
          provider_media_id: "157336",
          title: "Interstellar",
          year: 2014,
          season_number: null,
          status: "processing",
          terminal: false,
          active: true,
          can_cancel: true,
          recovery_required: false,
          created_at: "2026-09-13T04:00:00Z",
          updated_at: "2026-09-13T04:40:00Z",
          available_at: null
        }
      ]
    });

    const requests = await readRequests({
      expectedUserId: USER_ID
    });

    expect(requests).toHaveLength(1);

    expect(requests[0]).toMatchObject({
      requestId: REQUEST_ID,
      status: "processing",
      terminal: false,
      active: true
    });
  });
});
