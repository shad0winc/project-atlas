import type { DashboardMediaLibrary } from "../types/dashboard-media";

import { MediaLibraryCard } from "./MediaLibraryCard";

type MediaLibraryGridProps = Readonly<{
  libraries: readonly DashboardMediaLibrary[];
}>;

export function MediaLibraryGrid({ libraries }: MediaLibraryGridProps): React.ReactElement {
  if (!libraries.length) {
    return (
      <section aria-label="Media libraries" className="dashboard-empty-state">
        <h3>No media statistics are available</h3>

        <p>Atlas has not returned any media library data.</p>
      </section>
    );
  }

  return (
    <section aria-label="Media libraries" className="dashboard-metric-grid">
      {libraries.map((library) => (
        <MediaLibraryCard key={library.id} library={library} />
      ))}
    </section>
  );
}
