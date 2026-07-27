import { summarizeMediaSnapshot, type MediaSnapshot } from "../types/media";

import { MediaLibraryGrid } from "./MediaLibraryGrid";
import { MediaSummary } from "./MediaSummary";

type MediaOverviewProps = Readonly<{
  snapshot: MediaSnapshot;
}>;

export function MediaOverview({ snapshot }: MediaOverviewProps): React.ReactElement {
  const summary = summarizeMediaSnapshot(snapshot);

  return (
    <div className="media-overview">
      <MediaSummary summary={summary} />

      <section aria-labelledby="media-libraries-title" className="media-library-section">
        <header className="media-section-header">
          <div>
            <p className="portal-page-eyebrow">Libraries</p>

            <h2 id="media-libraries-title">Configured media libraries</h2>
          </div>

          <p>
            Updated{" "}
            <time dateTime={snapshot.generatedAt}>
              {new Date(snapshot.generatedAt).toLocaleString("en-US")}
            </time>
          </p>
        </header>

        <MediaLibraryGrid libraries={snapshot.libraries} />
      </section>
    </div>
  );
}
