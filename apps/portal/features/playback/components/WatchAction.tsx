import Link from "next/link";

type WatchActionProps = Readonly<{
  provider: string;
  itemId: string;
  label?: string;
}>;

export function WatchAction({
  provider,
  itemId,
  label = "Watch Now"
}: WatchActionProps): React.ReactElement {
  const query = new URLSearchParams({
    provider,
    item: itemId
  });

  return (
    <Link
      className="media-discovery-primary-button"
      href={`/portal/theater?${query.toString()}`}
    >
      {label}
    </Link>
  );
}
