"use client";

import { useEffect } from "react";

import { useMedia } from "../hooks/use-media";

import { MediaError } from "./MediaError";
import { MediaOverview } from "./MediaOverview";
import { MediaSkeleton } from "./MediaSkeleton";

type MediaViewProps = Readonly<{
  onRefreshStateChange?: (refresh: () => void, isRefreshing: boolean) => void;
}>;

export function MediaView({ onRefreshStateChange }: MediaViewProps = {}): React.ReactElement {
  const { state, refresh } = useMedia();
  const isRefreshing = state.status === "loading";

  useEffect(() => {
    onRefreshStateChange?.(refresh, isRefreshing);
  }, [isRefreshing, onRefreshStateChange, refresh]);

  if (state.status === "loading") {
    return <MediaSkeleton />;
  }

  if (state.status === "error") {
    return <MediaError message={state.error.message} onRetry={refresh} />;
  }

  return <MediaOverview snapshot={state.data} />;
}
