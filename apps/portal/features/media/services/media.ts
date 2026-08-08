import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

import {
  createMediaSnapshot,
  type MediaLibrary,
  type MediaLibraryStatus,
  type MediaSnapshot
} from "../types/media";

export type ReadMediaSnapshotOptions = Readonly<{
  signal?: AbortSignal;
}>;

/**
 * Transport-only response shape currently returned by `/dashboard/media`.
 *
 * These DTOs deliberately belong to the Media adapter rather than the
 * Dashboard feature. They describe the temporary wire contract and are mapped
 * immediately into Media-owned domain models.
 */
type MediaLibraryTransportResponse = Readonly<{
  id: string;
  label: string;
  count: number | null;
  status: MediaLibraryStatus;
  detail: string | null;
}>;

type MediaSnapshotTransportResponse = Readonly<{
  generated_at: string;
  libraries: readonly MediaLibraryTransportResponse[];
}>;

function mapMediaLibrary(library: MediaLibraryTransportResponse): MediaLibrary {
  return {
    id: library.id,
    label: library.label,
    status: library.status,
    ...(library.count === null ? {} : { count: library.count }),
    ...(library.detail === null ? {} : { detail: library.detail })
  };
}

/**
 * Load the Media feature snapshot through the currently available API route.
 *
 * The endpoint path remains temporary. Neither Dashboard transport names nor
 * Dashboard domain models cross this adapter boundary.
 */
export async function readMediaSnapshot({
  signal
}: ReadMediaSnapshotOptions = {}): Promise<MediaSnapshot> {
  const response = await authenticatedAtlasApiRequest<MediaSnapshotTransportResponse>(
    "/dashboard/media",
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  return createMediaSnapshot({
    generatedAt: response.generated_at,
    libraries: response.libraries.map(mapMediaLibrary)
  });
}
