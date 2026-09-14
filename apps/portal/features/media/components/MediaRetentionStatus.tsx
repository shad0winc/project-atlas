import type { MediaRetention } from "../types/retention";

export type MediaRetentionStatusProps = Readonly<{
  retention: MediaRetention;
}>;

function authoritativeDeletionTime(
  deleteAt: string | null
): React.ReactElement | null {
  if (deleteAt === null) {
    return null;
  }

  return (
    <>
      {" "}
      <time dateTime={deleteAt}>{deleteAt}</time>
    </>
  );
}

export function MediaRetentionStatus({
  retention
}: MediaRetentionStatusProps): React.ReactElement {
  const { lifecycle } = retention;

  if (lifecycle.state === "protected") {
    return (
      <p className="media-discovery-status">
        Protected from automatic deletion
      </p>
    );
  }

  if (lifecycle.state === "scheduled") {
    return (
      <p className="media-discovery-status">
        Scheduled for deletion:
        {authoritativeDeletionTime(lifecycle.deleteAt)}
      </p>
    );
  }

  if (lifecycle.state === "eligible") {
    return (
      <p className="media-discovery-status">
        Eligible for deletion:
        {authoritativeDeletionTime(lifecycle.deleteAt)}
      </p>
    );
  }

  return (
    <p className="media-discovery-status">
      Deletion schedule unavailable
    </p>
  );
}
