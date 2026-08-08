type MediaErrorProps = Readonly<{
  message: string;
  onRetry: () => void;
}>;

export function MediaError({ message, onRetry }: MediaErrorProps): React.ReactElement {
  return (
    <section aria-labelledby="media-error-title" className="media-message-panel" role="alert">
      <p className="portal-page-eyebrow">Media unavailable</p>

      <h2 id="media-error-title">Atlas could not load the media libraries</h2>

      <p>{message}</p>

      <button className="media-refresh-button" onClick={onRetry} type="button">
        Try again
      </button>
    </section>
  );
}
