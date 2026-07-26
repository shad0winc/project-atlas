type DashboardErrorProps = Readonly<{
  message: string;
  onRetry: () => void;
}>;

export function DashboardError({ message, onRetry }: DashboardErrorProps): React.ReactElement {
  return (
    <section aria-labelledby="dashboard-error-title" className="dashboard-error" role="alert">
      <div>
        <p className="dashboard-error-eyebrow">Dashboard unavailable</p>

        <h3 className="dashboard-error-title" id="dashboard-error-title">
          Atlas could not load operational data
        </h3>

        <p className="dashboard-error-message">{message}</p>
      </div>

      <button className="dashboard-retry-button" onClick={onRetry} type="button">
        Try again
      </button>
    </section>
  );
}
