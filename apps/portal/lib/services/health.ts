import { atlasApiRequest } from "../api/client";
import type { AtlasHealthResponse } from "../api/contracts";

export async function readAtlasHealth(): Promise<AtlasHealthResponse> {
  return atlasApiRequest<AtlasHealthResponse>("/health", {
    method: "GET",
    cache: "no-store"
  });
}
