import type { MediaLibrary } from "../types/media";

import { MediaLibraryCard } from "./MediaLibraryCard";

type MediaLibraryGridProps = Readonly<{
  libraries: readonly MediaLibrary[];
}>;

export function MediaLibraryGrid({ libraries }: MediaLibraryGridProps): React.ReactElement {
  if (!libraries.length) {
    return (
      <section aria-labelledby="media-empty-title" className="media-message-panel">
        <p className="portal-page-eyebrow">No statistics</p>

        <h2 id="media-empty-title">No media libraries were returned</h2>

        <p>
          Atlas completed the request successfully, but no configured library statistics are
          currently available.
        </p>
      </section>
    );
  }

  return (
    <section aria-label="Media libraries" className="media-library-grid">
      {libraries.map((library) => (
        <MediaLibraryCard key={library.id} library={library} />
      ))}
    </section>
  );
}
