"use client";

import { useRef, useState, type FormEvent } from "react";

import { useAuth } from "../../../lib/auth/use-auth";
import { ATLAS_PERMISSIONS } from "../../../lib/authorization/permissions";
import { usePermission } from "../../../lib/authorization/use-permission";
import { RequestCreationError, createPersonalMediaRequest } from "../../requests";

import {
  useMediaDiscovery,
  type MediaDiscoveryMode,
  type MediaDiscoveryState
} from "../hooks/use-media-discovery";
import {
  mediaDiscoveryAvailabilityLabel,
  type MediaDiscoveryItem,
  type MediaDiscoveryMediaType
} from "../types/discovery";

export type MediaDiscoveryRequestAction = Readonly<{
  status: "submitting" | "submitted" | "conflict" | "unconfirmed";
  message: string;
}>;

export type MediaDiscoveryRequestActions = Readonly<
  Record<string, MediaDiscoveryRequestAction | undefined>
>;

type MediaDiscoveryContentProps = Readonly<{
  state: MediaDiscoveryState;
  mode: MediaDiscoveryMode;
  mediaType: MediaDiscoveryMediaType;
  activeQuery: string;
  onBrowse: (mediaType: MediaDiscoveryMediaType) => void;
  onSearch: (query: string) => void;
  onPage: (page: number) => void;
  onRefresh: () => void;
  canCreateRequests: boolean;
  requestActions: MediaDiscoveryRequestActions;
  onRequestMovie: (item: MediaDiscoveryItem) => void;
}>;

function mediaTypeLabel(mediaType: MediaDiscoveryMediaType): string {
  return mediaType === "movie" ? "Movie" : "TV";
}

function mediaRequestKey(item: MediaDiscoveryItem): string {
  return `${item.mediaType}:${item.providerMediaId}`;
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
  onRefresh,
  canCreateRequests,
  requestActions,
  onRequestMovie
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
                  key={mediaRequestKey(item)}
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

                  <div className="media-discovery-request-area">
                    <p className="media-discovery-read-only">
                      {item.requestEligible
                        ? "Not currently tracked by the media provider."
                        : "This title is already tracked by the media provider."}
                    </p>

                    {(() => {
                      const requestAction = requestActions[mediaRequestKey(item)];

                      if (!item.requestEligible) {
                        return null;
                      }

                      if (item.mediaType === "tv") {
                        return canCreateRequests ? (
                          <p className="media-discovery-request-message">
                            Choose a season before requesting TV. TV request actions are not enabled
                            yet.
                          </p>
                        ) : null;
                      }

                      if (!canCreateRequests) {
                        return null;
                      }

                      return (
                        <>
                          <button
                            aria-busy={requestAction?.status === "submitting"}
                            className="media-discovery-primary-button media-discovery-request-button"
                            disabled={requestAction !== undefined}
                            onClick={() => onRequestMovie(item)}
                            type="button"
                          >
                            {requestAction?.status === "submitting"
                              ? "Requesting…"
                              : requestAction?.status === "submitted"
                                ? "Requested"
                                : requestAction?.status === "conflict"
                                  ? "Already requested"
                                  : requestAction?.status === "unconfirmed"
                                    ? "Check requests"
                                    : "Request movie"}
                          </button>

                          {requestAction ? (
                            <p aria-live="polite" className="media-discovery-request-message">
                              {requestAction.message}
                            </p>
                          ) : null}
                        </>
                      );
                    })()}
                  </div>
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
  const { user } = useAuth();
  const { can } = usePermission();

  const canCreateRequests = user !== null && can(ATLAS_PERMISSIONS.requestsCreate);

  // A target enters this set before the POST begins and
  // remains blocked until the page is remounted. This is
  // presentation-level repeat-submit protection only;
  // B3.3.1 remains the authoritative server invariant.
  const blockedRequestKeys = useRef(new Set<string>());

  const [requestActions, setRequestActions] = useState<MediaDiscoveryRequestActions>({});

  const handleRequestMovie = async (item: MediaDiscoveryItem): Promise<void> => {
    if (item.mediaType !== "movie" || !item.requestEligible || !canCreateRequests || !user) {
      return;
    }

    const key = mediaRequestKey(item);

    if (blockedRequestKeys.current.has(key) || requestActions[key] !== undefined) {
      return;
    }

    blockedRequestKeys.current.add(key);

    setRequestActions((current) => ({
      ...current,
      [key]: {
        status: "submitting",
        message: `Submitting ${item.title} to Atlas…`
      }
    }));

    try {
      await createPersonalMediaRequest(
        {
          mediaType: "movie",
          providerMediaId: item.providerMediaId,
          title: item.title,
          ...(item.year === undefined
            ? {}
            : {
                year: item.year
              })
        },
        {
          expectedUserId: user.user_id
        }
      );

      setRequestActions((current) => ({
        ...current,
        [key]: {
          status: "submitted",
          message: `${item.title} was submitted to Atlas.`
        }
      }));
    } catch (error: unknown) {
      if (error instanceof RequestCreationError && error.kind === "conflict") {
        setRequestActions((current) => ({
          ...current,
          [key]: {
            status: "conflict",
            message: error.message
          }
        }));

        return;
      }

      const message =
        error instanceof RequestCreationError
          ? error.message
          : "Atlas did not confirm this request. Review Your requests before trying again.";

      setRequestActions((current) => ({
        ...current,
        [key]: {
          status: "unconfirmed",
          message
        }
      }));
    }
  };

  return (
    <MediaDiscoveryContent
      activeQuery={discovery.activeQuery}
      canCreateRequests={canCreateRequests}
      mediaType={discovery.mediaType}
      mode={discovery.mode}
      onBrowse={discovery.browse}
      onPage={discovery.goToPage}
      onRefresh={discovery.refresh}
      onRequestMovie={(item) => {
        void handleRequestMovie(item);
      }}
      onSearch={discovery.search}
      requestActions={requestActions}
      state={discovery.state}
    />
  );
}
