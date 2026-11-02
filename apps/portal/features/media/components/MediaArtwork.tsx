"use client";

import { useEffect, useState } from "react";
import { discoveryArtworkSource, readCatalogArtwork } from "../services/artwork";

type PosterProps = Readonly<{ title: string; year?: number; source?: string; loading?: boolean }>;

export function MediaPoster({ title, year, source, loading = false }: PosterProps): React.ReactElement {
  const [failedSource, setFailedSource] = useState<string>();
  const label = `${title}${year === undefined ? "" : ` (${year})`} poster`;
  return (
    <div className="media-artwork" aria-busy={loading}>
      {source !== undefined && source !== failedSource ? (
        // The source is a validated provider image or authenticated image bytes.
        // eslint-disable-next-line @next/next/no-img-element
        <img alt={label} src={source} width={160} height={240} loading="lazy"
          decoding="async" referrerPolicy="no-referrer" onError={() => setFailedSource(source)} />
      ) : <span className="media-artwork-fallback" role="img" aria-label={`${label} unavailable`}>
        {loading ? "Loading artwork…" : "No artwork available"}
      </span>}
    </div>
  );
}

export function DiscoveryArtwork({ title, year, posterPath }: Readonly<{
  title: string; year?: number; posterPath?: string;
}>): React.ReactElement {
  return <MediaPoster title={title} year={year} source={discoveryArtworkSource(posterPath)} />;
}

export function CatalogArtwork({ title, year, itemId, provider }: Readonly<{
  title: string; year?: number; itemId: string; provider: string;
}>): React.ReactElement {
  const identity = `${provider}:${itemId}`;
  const [image, setImage] = useState<Readonly<{ identity: string; source?: string }>>();
  useEffect(() => {
    const controller = new AbortController();
    if (provider === "jellyfin") {
      void readCatalogArtwork(itemId, controller.signal).then(
        source => { if (!controller.signal.aborted) setImage({ identity, source }); },
        () => { if (!controller.signal.aborted) setImage({ identity }); }
      );
    }
    return () => controller.abort();
  }, [identity, itemId, provider]);
  const current = image?.identity === identity ? image : undefined;
  return <MediaPoster title={title} year={year} source={current?.source}
    loading={provider === "jellyfin" && current === undefined} />;
}
