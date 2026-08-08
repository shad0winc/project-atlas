export function MediaSkeleton(): React.ReactElement {
  return (
    <section aria-busy="true" aria-label="Loading media libraries" className="media-library-grid">
      {Array.from({ length: 7 }, (_, index) => (
        <article
          aria-hidden="true"
          className="media-library-card media-library-card-loading"
          key={index}
        >
          <span className="media-loading-line media-loading-line-short" />
          <span className="media-loading-line media-loading-line-value" />
          <span className="media-loading-line" />
        </article>
      ))}
    </section>
  );
}
