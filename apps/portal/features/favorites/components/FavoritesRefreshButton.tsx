"use client";

type FavoritesRefreshButtonProps = Readonly<{
  disabled?: boolean;
  onRefresh: () => void;
}>;

export function FavoritesRefreshButton({
  disabled = false,
  onRefresh
}: FavoritesRefreshButtonProps): React.ReactElement {
  return (
    <button
      className="favorites-refresh-button"
      disabled={disabled}
      onClick={onRefresh}
      type="button"
    >
      {disabled ? "Refreshing…" : "Refresh favorites"}
    </button>
  );
}
