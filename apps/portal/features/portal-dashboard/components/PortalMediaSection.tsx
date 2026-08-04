import type { DashboardMediaSnapshot } from "../../dashboard/types/dashboard-media";

import { MediaLibraryGrid } from "../../dashboard/components/MediaLibraryGrid";

type PortalMediaSectionProps = Readonly<{
  media: DashboardMediaSnapshot;
}>;

export function PortalMediaSection({ media }: PortalMediaSectionProps): React.ReactElement {
  return (
    <section aria-labelledby="portal-media-heading" className="dashboard-runtime">
      <header>
        <h2 id="portal-media-heading">Media libraries</h2>

        <p>Current library totals collected by Atlas Retention Intelligence.</p>
      </header>

      <MediaLibraryGrid libraries={media.libraries} />

      <p className="dashboard-generated-at">
        Media statistics updated{" "}
        <time dateTime={media.generatedAt}>{new Date(media.generatedAt).toLocaleString()}</time>
      </p>
    </section>
  );
}
