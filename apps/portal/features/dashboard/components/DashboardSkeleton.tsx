type DashboardSkeletonProps = Readonly<{
  cardCount?: number;
}>;

export function DashboardSkeleton({ cardCount = 4 }: DashboardSkeletonProps): React.ReactElement {
  const normalizedCardCount = Math.max(1, Math.min(cardCount, 12));

  return (
    <section aria-busy="true" aria-label="Loading dashboard" className="dashboard-metric-grid">
      {Array.from(
        {
          length: normalizedCardCount
        },
        (_, index) => (
          <div aria-hidden="true" className="dashboard-skeleton-card" key={index}>
            <span className="dashboard-skeleton-line dashboard-skeleton-line-short" />
            <span className="dashboard-skeleton-line dashboard-skeleton-line-value" />
            <span className="dashboard-skeleton-line" />
            <span className="dashboard-skeleton-line dashboard-skeleton-line-medium" />
          </div>
        )
      )}
    </section>
  );
}
