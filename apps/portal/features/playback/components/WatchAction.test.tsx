import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WatchAction } from "./WatchAction";

describe("WatchAction", () => {
  it("routes playback through Atlas Theater", () => {
    const markup = renderToStaticMarkup(
      <WatchAction
        provider="jellyfin"
        itemId="item 123"
      />
    );

    expect(markup).toContain(
      'href="/portal/theater?provider=jellyfin&amp;item=item+123"'
    );
    expect(markup).toContain("Watch Now");
    expect(markup).not.toContain("192.168.");
    expect(markup).not.toContain("api_key");
  });
});
