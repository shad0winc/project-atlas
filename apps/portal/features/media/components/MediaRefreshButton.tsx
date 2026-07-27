"use client";

type MediaRefreshButtonProps = Readonly<{
  disabled?: boolean;
  onRefresh: () => void;
}>;

export function MediaRefreshButton({
  disabled = false,
  onRefresh
}: MediaRefreshButtonProps): React.ReactElement {
  return (
    <button className="media-refresh-button" disabled={disabled} onClick={onRefresh} type="button">
      {disabled ? "Refreshing…" : "Refresh libraries"}
    </button>
  );
}
