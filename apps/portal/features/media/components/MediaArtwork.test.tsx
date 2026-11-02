// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { CatalogArtwork, DiscoveryArtwork, MediaPoster } from "./MediaArtwork";
import { readCatalogArtwork } from "../services/artwork";
vi.mock("../services/artwork", async importOriginal => ({
  ...await importOriginal<typeof import("../services/artwork")>(), readCatalogArtwork: vi.fn()
}));
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const host = document.createElement("div");document.body.append(host);
let root = createRoot(host);
afterEach(async () => { await act(async () => root.unmount());root = createRoot(host); });
it("preserves title and year in accessible artwork identity", async () => {
  await act(async () => root.render(<DiscoveryArtwork title="The Gentlemen" year={2024} posterPath="/poster.jpg" />));
  expect(host.querySelector("img")?.alt).toBe("The Gentlemen (2024) poster");
  expect(host.querySelector("img")?.referrerPolicy).toBe("no-referrer");
});
it("has a clear fallback for missing and failed images", async () => {
  await act(async () => root.render(<MediaPoster title="Movie" source="https://image.tmdb.org/t/p/w342/a.jpg" />));
  await act(async () => host.querySelector("img")!.dispatchEvent(new Event("error")));
  expect(host.textContent).toContain("No artwork available");
  await act(async () => root.render(<MediaPoster title="Movie" source="https://image.tmdb.org/t/p/w342/b.jpg" />));
  expect(host.querySelector("img")?.getAttribute("src")).toContain("b.jpg");
});
it("does not reuse a stale image after item identity changes", async () => {
  vi.mocked(readCatalogArtwork).mockResolvedValueOnce("data:image/jpeg;base64,Zmlyc3Q=");
  await act(async () => root.render(<CatalogArtwork title="First" itemId="first" provider="jellyfin" />));
  expect(host.querySelector("img")?.alt).toBe("First poster");
  let finish: (value: string) => void = () => {};
  vi.mocked(readCatalogArtwork).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
  await act(async () => root.render(<CatalogArtwork title="Second" itemId="second" provider="jellyfin" />));
  expect(host.querySelector("img")).toBeNull();
  await act(async () => finish("data:image/jpeg;base64,c2Vjb25k"));
  expect(host.querySelector("img")?.alt).toBe("Second poster");
});
it("uses a fallback when authenticated library artwork is unavailable", async () => {
  vi.mocked(readCatalogArtwork).mockRejectedValueOnce(new Error("unavailable"));
  await act(async () => root.render(<CatalogArtwork title="Missing" itemId="missing" provider="jellyfin" />));
  expect(host.textContent).toContain("No artwork available");
});
it("aborts the artwork request on unmount", async () => {
  let signal: AbortSignal | undefined;
  vi.mocked(readCatalogArtwork).mockImplementationOnce((_, value) => { signal=value;return new Promise(() => {}); });
  await act(async () => root.render(<CatalogArtwork title="Movie" itemId="movie" provider="jellyfin" />));
  await act(async () => root.render(null));
  expect(signal?.aborted).toBe(true);
});
