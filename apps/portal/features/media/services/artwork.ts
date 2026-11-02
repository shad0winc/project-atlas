import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

const artworkTypes = new Set(["image/jpeg", "image/png", "image/webp", "image/avif"]);

export function discoveryArtworkSource(posterPath: string | undefined): string | undefined {
  // Accept only a provider image filename, never an arbitrary URL or path traversal.
  if (posterPath === undefined || !/^\/[A-Za-z0-9_-]{1,200}\.(jpg|jpeg|png|webp)$/i.test(posterPath)) {
    return undefined;
  }
  return `https://image.tmdb.org/t/p/w342${posterPath}`;
}

export async function readCatalogArtwork(itemId: string, signal: AbortSignal): Promise<string> {
  if (!/^[A-Za-z0-9_-]{1,128}$/.test(itemId)) throw new Error("Artwork is unavailable.");
  const value = await authenticatedAtlasApiRequest<{ media_type: string; data_base64: string }>(
    `/media/catalog/${encodeURIComponent(itemId)}/artwork`,
    { method: "GET", cache: "no-store", signal }
  );
  if (!artworkTypes.has(value.media_type) || typeof value.data_base64 !== "string" ||
      value.data_base64.length === 0 || value.data_base64.length > 349528 ||
      !/^[A-Za-z0-9+/]+={0,2}$/.test(value.data_base64)) {
    throw new Error("Artwork is unavailable.");
  }
  return `data:${value.media_type};base64,${value.data_base64}`;
}
