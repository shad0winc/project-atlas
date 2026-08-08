import type { MediaLibrary } from "../types/media";

type MediaLibraryCardProps = Readonly<{
  library: MediaLibrary;
}>;

function displayCount(library: MediaLibrary): string {
  if (library.status === "unavailable" || library.count === undefined) {
    return "Unavailable";
  }

  return library.count.toLocaleString("en-US");
}

export function MediaLibraryCard({ library }: MediaLibraryCardProps): React.ReactElement {
  const headingId = `media-library-${library.id}`;

  return (
    <article
      aria-labelledby={headingId}
      className="media-library-card"
      data-status={library.status}
    >
      <header className="media-library-card-header">
        <h3 id={headingId}>{library.label}</h3>

        <span className="media-library-status">
          {library.status === "available" ? "Available" : "Unavailable"}
        </span>
      </header>

      <strong className="media-library-count">{displayCount(library)}</strong>

      <p className="media-library-description">
        {library.status === "available"
          ? "Items currently represented in this Atlas library."
          : "Atlas cannot currently retrieve statistics for this library."}
      </p>

      {library.detail ? <p className="media-library-detail">{library.detail}</p> : null}
    </article>
  );
}
