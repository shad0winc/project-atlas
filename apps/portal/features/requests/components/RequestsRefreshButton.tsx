"use client";

type RequestsRefreshButtonProps = Readonly<{
  disabled?: boolean;
  onRefresh: () => void;
}>;

export function RequestsRefreshButton({
  disabled = false,
  onRefresh
}: RequestsRefreshButtonProps): React.ReactElement {
  return (
    <button
      className="requests-refresh-button"
      disabled={disabled}
      onClick={onRefresh}
      type="button"
    >
      {disabled ? "Refreshing…" : "Refresh requests"}
    </button>
  );
}
