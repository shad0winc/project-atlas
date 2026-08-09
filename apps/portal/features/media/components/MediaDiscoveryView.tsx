"use client";

import { useState, type FormEvent } from "react";

import {
  useMediaDiscovery,
  type MediaDiscoveryMode,
  type MediaDiscoveryState
} from "../hooks/use-media-discovery";
import { mediaDiscoveryAvailabilityLabel, type MediaDiscoveryMediaType } from "../types/discovery";

type MediaDiscoveryContentProps = Readonly<{
  state: MediaDiscoveryState;
  mode: MediaDiscoveryMode;
  mediaType: MediaDiscoveryMediaType;
  activeQuery: string;
  onBrowse: (mediaType: MediaDiscoveryMediaType) => void;
  onSearch: (query: string) => void;
  onPage: (page: number) => void;
  onRefresh: () => void;
}>;

function mediaTypeLabel(mediaType: MediaDiscoveryMediaType): string {
  return mediaType === "movie" ? "Movie" : "TV";
}

function DiscoveryLoading(): React.ReactElement {
  return (
    <div
      aria-busy="true"
      aria-label="Loading media discovery results"
      className="media-discovery-grid"
    >
      {Array.from({ length: 6 }, (_, index) => (
        <article className="media-discovery-card media-discovery-card-loading" key={index}>
          <span className="media-discovery-loading-line media-discovery-loading-line-short" />
          <span className="media-discovery-loading-line media-discovery-loading-line-title" />
          <span className="media-discovery-loading-line" />
          <span className="media-discovery-loading-line" />
        </article>
      ))}
    </div>
  );
}

export function MediaDiscoveryContent({
  state,
  mode,
  mediaType,
  activeQuery,
  onBrowse,
  onSearch,
  onPage,
  onRefresh
}: MediaDiscoveryContentProps): React.ReactElement {
  const [searchText, setSearchText] = useState(activeQuery);

  const isLoading = state.status === "loading";

  const handleBrowse = (nextMediaType: MediaDiscoveryMediaType): void => {
    setSearchText("");
    onBrowse(nextMediaType);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();

    const query = searchText.trim();

    if (!query) {
      return;
    }

    setSearchText(query);
    onSearch(query);
  };

  return (
    <section aria-label="Media discovery" className="media-discovery-view">
      <div className="media-discovery-controls">
        <form className="media-discovery-search" onSubmit={handleSubmit}>
          <label htmlFor="atlas-media-search">Search movies and TV shows</label>

          <div className="media-discovery-search-row">
            <input
              id="atlas-media-search"
              maxLength={200}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="Search by title"
              type="search"
              value={searchText}
            />

            <button
              className="media-discovery-primary-button"
              disabled={searchText.trim().length === 0}
              type="submit"
            >
              Search
            </button>
          </div>
        </form>

        <div aria-label="Browse media type" className="media-discovery-tabs" role="group">
          <button
            aria-pressed={mode === "discover" && mediaType === "movie"}
            className="media-discovery-secondary-button"
            onClick={() => handleBrowse("movie")}
            type="button"
          >
            Movies
          </button>

          <button
            aria-pressed={mode === "discover" && mediaType === "tv"}
            className="media-discovery-secondary-button"
            onClick={() => handleBrowse("tv")}
            type="button"
          >
            TV shows
          </button>

          <button
            className="media-discovery-secondary-button"
            disabled={isLoading}
            onClick={onRefresh}
            type="button"
          >
            {isLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>

      {state.status === "loading" ? <DiscoveryLoading /> : null}

      {state.status === "error" ? (
        <section className="media-discovery-message" role="alert">
          <h2>Media discovery is unavailable</h2>
          <p>{state.error.message}</p>
          <button className="media-discovery-secondary-button" onClick={onRefresh} type="button">
            Try again
          </button>
        </section>
      ) : null}

      {state.status === "ready" ? (
        <>
          <header className="media-discovery-results-header">
            <div>
              <p className="media-discovery-eyebrow">
                {mode === "search"
                  ? `Search results for “${activeQuery}”`
                  : mediaType === "movie"
                    ? "Movie discovery"
                    : "TV discovery"}
              </p>
              <h2>{mode === "search" ? "Search results" : "Browse media"}</h2>
            </div>

            <p aria-live="polite" className="media-discovery-page-status">
              {state.data.totalPages === 0
                ? "No result pages"
                : `Page ${state.data.page} of ${state.data.totalPages}`}
            </p>
          </header>

          {state.data.items.length === 0 ? (
            <section className="media-discovery-message">
              <h3>No media results</h3>
              <p>
                {mode === "search"
                  ? "Atlas did not find a matching movie or TV show."
                  : "Atlas did not receive any media for this discovery page."}
              </p>
            </section>
          ) : (
            <div className="media-discovery-grid">
              {state.data.items.map((item) => (
                <article
                  className="media-discovery-card"
                  data-request-eligible={item.requestEligible ? "true" : "false"}
                  key={`${item.mediaType}:${item.providerMediaId}`}
                >
                  <header className="media-discovery-card-header">
                    <div>
                      <p className="media-discovery-kind">
                        {mediaTypeLabel(item.mediaType)}
                        {item.year === undefined ? "" : ` · ${item.year}`}
                      </p>
                      <h3>{item.title}</h3>
                    </div>

                    <span className="media-discovery-status" data-availability={item.availability}>
                      {mediaDiscoveryAvailabilityLabel(item.availability)}
                    </span>
                  </header>

                  <p className="media-discovery-overview">
                    {item.overview ?? "No overview is available for this title."}
                  </p>

                  <p className="media-discovery-read-only">
                    {item.requestEligible
                      ? "Not currently tracked by the media provider."
                      : "This title is already tracked by the media provider."}
                  </p>
                </article>
              ))}
            </div>
          )}

          <nav aria-label="Media discovery pages" className="media-discovery-pagination">
            <button
              className="media-discovery-secondary-button"
              disabled={state.data.page <= 1}
              onClick={() => onPage(state.data.page - 1)}
              type="button"
            >
              Previous
            </button>

            <button
              className="media-discovery-secondary-button"
              disabled={state.data.nextPage === null}
              onClick={() => {
                if (state.data.nextPage !== null) {
                  onPage(state.data.nextPage);
                }
              }}
              type="button"
            >
              Next
            </button>
          </nav>
        </>
      ) : null}
    </section>
  );
}

export function MediaDiscoveryView(): React.ReactElement {
  const discovery = useMediaDiscovery();

  return (
    <MediaDiscoveryContent
      activeQuery={discovery.activeQuery}
      mediaType={discovery.mediaType}
      mode={discovery.mode}
      onBrowse={discovery.browse}
      onPage={discovery.goToPage}
      onRefresh={discovery.refresh}
      onSearch={discovery.search}
      state={discovery.state}
    />
  );
}
