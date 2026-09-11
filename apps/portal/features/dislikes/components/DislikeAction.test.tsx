import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const { addDislikeMock } = vi.hoisted(() => ({
  addDislikeMock: vi.fn()
}));

vi.mock("../api/dislikes", () => ({
  addDislike: addDislikeMock
}));

import { DislikeAction } from "./DislikeAction";

const USER_ID =
  "usr_0123456789abcdef0123456789abcdef";

describe("DislikeAction", () => {
  it("renders the explicit 24-hour cleanup action without exposing owner identity", () => {
    const markup = renderToStaticMarkup(
      <DislikeAction
        expectedUserId={USER_ID}
        itemId="episode-1"
        provider="jellyfin"
        title="Example Episode"
      />
    );

    expect(markup).toContain("Dislike");
    expect(markup).toContain("24 hours");
    expect(markup).not.toContain(USER_ID);
  });
});
