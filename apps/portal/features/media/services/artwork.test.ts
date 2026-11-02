import { describe, expect, it, vi } from "vitest";
import { discoveryArtworkSource, readCatalogArtwork } from "./artwork";
import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";
vi.mock("../../../lib/services/authenticated", () => ({ authenticatedAtlasApiRequest: vi.fn() }));

describe("exact media artwork", () => {
  it("uses only the selected provider image filename", () => {
    expect(discoveryArtworkSource("/ExactPoster123.jpg")).toBe("https://image.tmdb.org/t/p/w342/ExactPoster123.jpg");
  });
  it.each([undefined, "//elsewhere/image.jpg", "/../image.jpg", "/image.jpg?token=x", "https://elsewhere/image.jpg", "/image.svg", "/%2e%2e.jpg"])("rejects unsafe or absent poster paths: %s", value => {
    expect(discoveryArtworkSource(value)).toBeUndefined();
  });
  it("requests exact library artwork through the authenticated client", async () => {
    vi.mocked(authenticatedAtlasApiRequest).mockResolvedValue({ media_type: "image/jpeg", data_base64: "/9j/Zml4dHVyZQ==" });
    const signal = new AbortController().signal;
    await expect(readCatalogArtwork("item-1", signal)).resolves.toBe("data:image/jpeg;base64,/9j/Zml4dHVyZQ==");
    expect(authenticatedAtlasApiRequest).toHaveBeenCalledWith("/media/catalog/item-1/artwork", { method: "GET", cache: "no-store", signal });
  });
  it.each([
    { media_type: "image/svg+xml", data_base64: "PHN2Zz4=" },
    { media_type: "image/jpeg", data_base64: "https://private?token=x" },
    { media_type: "image/jpeg", data_base64: "x".repeat(349529) },
    { media_type: "image/jpeg", data_base64: "" }
  ])("rejects unsupported bytes and oversized responses", async value => {
    vi.mocked(authenticatedAtlasApiRequest).mockResolvedValue(value);
    await expect(readCatalogArtwork("item-1", new AbortController().signal)).rejects.toThrow("Artwork is unavailable.");
  });
});
