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
import { readMediaSeriesDetail } from "../services/series";
import {
  mediaDiscoveryAvailabilityLabel,
  type MediaDiscoveryItem,
  type MediaDiscoveryMediaType
} from "../types/discovery";
import {
  mediaSeriesRequestType,
  type MediaSeriesDetail,
  type MediaSeriesSeason
} from "../types/series";

export type MediaDiscoveryRequestAction = Readonly<{
  status: "submitting" | "submitted" | "conflict" | "unconfirmed";
  message: string;
}>;

export type MediaDiscoveryRequestActions = Readonly<
  Record<string, MediaDiscoveryRequestAction | undefined>
>;

export type MediaDiscoverySeriesState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "ready"; detail: MediaSeriesDetail }>
  | Readonly<{ status: "error"; message: string }>;

export type MediaDiscoverySeriesStates = Readonly<
  Record<string, MediaDiscoverySeriesState | undefined>
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
  seriesStates: MediaDiscoverySeriesStates;
  onLoadTvSeasons: (item: MediaDiscoveryItem) => void;
  onRequestMovie: (item: MediaDiscoveryItem) => void;
  onRequestTvSeason: (
    item: MediaDiscoveryItem,
    detail: MediaSeriesDetail,
    season: MediaSeriesSeason
  ) => void;
}>;

function mediaTypeLabel(mediaType: MediaDiscoveryMediaType): string {
  return mediaType === "movie" ? "Movie" : "TV";
}

function mediaRequestKey(item: MediaDiscoveryItem): string {
  return `${item.mediaType}:${item.providerMediaId}`;
}

function tvSeasonRequestKey(detail: MediaSeriesDetail, season: MediaSeriesSeason): string {
  return `${mediaSeriesRequestType(detail)}:${detail.providerMediaId}:season:${season.seasonNumber}`;
}

function requestButtonLabel(
  action: MediaDiscoveryRequestAction | undefined,
  idleLabel: string
): string {
  switch (action?.status) {
    case "submitting":
      return "Requesting…";
    case "submitted":
      return "Requested";
    case "conflict":
      return "Already requested";
    case "unconfirmed":
      return "Check requests";
    default:
      return idleLabel;
  }
}

function seasonUnavailableMessage(season: MediaSeriesSeason): string {
  if (!season.requestabilityKnown) {
    return "Request availability is currently unavailable for this season.";
  }

  if (season.availability === "available") {
    return "This season is already available.";
  }

  if (season.availability === "pending" || season.availability === "processing") {
    return "This season is already being processed.";
  }

  if (season.availability === "partially_available") {
    return "This season is already partially available or tracked.";
  }

  if (season.availability === "blocklisted") {
    return "This season is not currently requestable.";
  }

  return "This season is not currently requestable.";
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

function TvSeasonSelection({
  item,
  canCreateRequests,
  requestActions,
  seriesState,
  onLoadTvSeasons,
  onRequestTvSeason
}: Readonly<{
  item: MediaDiscoveryItem;
  canCreateRequests: boolean;
  requestActions: MediaDiscoveryRequestActions;
  seriesState: MediaDiscoverySeriesState | undefined;
  onLoadTvSeasons: (item: MediaDiscoveryItem) => void;
  onRequestTvSeason: (
    item: MediaDiscoveryItem,
    detail: MediaSeriesDetail,
    season: MediaSeriesSeason
  ) => void;
}>): React.ReactElement {
  if (seriesState === undefined) {
    return (
      <button
        className="media-discovery-secondary-button"
        onClick={() => onLoadTvSeasons(item)}
        type="button"
      >
        View seasons
      </button>
    );
  }

  if (seriesState.status === "loading") {
    return (
      <button aria-busy="true" className="media-discovery-secondary-button" disabled type="button">
        Loading seasons…
      </button>
    );
  }

  if (seriesState.status === "error") {
    return (
      <>
        <p className="media-discovery-request-message" role="alert">
          {seriesState.message}
        </p>
        <button
          className="media-discovery-secondary-button"
          onClick={() => onLoadTvSeasons(item)}
          type="button"
        >
          Retry seasons
        </button>
      </>
    );
  }

  const detail = seriesState.detail;

  return (
    <section aria-label={`Seasons for ${item.title}`} className="media-discovery-request-area">
      <p className="media-discovery-request-message">
        {detail.isAnime ? "Anime series" : "TV series"}
        {detail.isOngoing ? " · Ongoing" : ""}
      </p>

      {detail.seasons.length === 0 ? (
        <p className="media-discovery-request-message">
          No requestable season metadata is available.
        </p>
      ) : (
        <ul>
          {detail.seasons.map((season) => {
            const requestAction = requestActions[tvSeasonRequestKey(detail, season)];

            return (
              <li key={season.seasonNumber}>
                <p>
                  <strong>{season.name}</strong>
                  {` · ${season.episodeCount} episode${season.episodeCount === 1 ? "" : "s"}`}
                  {` · ${mediaDiscoveryAvailabilityLabel(season.availability)}`}
                </p>

                {season.requestEligible && season.requestabilityKnown ? (
                  canCreateRequests ? (
                    <>
                      <button
                        aria-busy={requestAction?.status === "submitting"}
                        className="media-discovery-primary-button media-discovery-request-button"
                        disabled={requestAction !== undefined}
                        onClick={() => onRequestTvSeason(item, detail, season)}
                        type="button"
                      >
                        {requestButtonLabel(requestAction, `Request ${season.name}`)}
                      </button>

                      {requestAction ? (
                        <p aria-live="polite" className="media-discovery-request-message">
                          {requestAction.message}
                        </p>
                      ) : null}
                    </>
                  ) : null
                ) : (
                  <p className="media-discovery-request-message">
                    {seasonUnavailableMessage(season)}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <p className="media-discovery-read-only">
        Season selection controls this Atlas request only. Future-season monitoring is configured
        separately by the media service.
      </p>
    </section>
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
  seriesStates,
  onLoadTvSeasons,
  onRequestMovie,
  onRequestTvSeason
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
              {state.data.items.map((item) => {
                const itemKey = mediaRequestKey(item);

                return (
                  <article
                    className="media-discovery-card"
                    data-request-eligible={item.requestEligible ? "true" : "false"}
                    key={itemKey}
                  >
                    <header className="media-discovery-card-header">
                      <div>
                        <p className="media-discovery-kind">
                          {mediaTypeLabel(item.mediaType)}
                          {item.year === undefined ? "" : ` · ${item.year}`}
                        </p>
                        <h3>{item.title}</h3>
                      </div>

                      <span
                        className="media-discovery-status"
                        data-availability={item.availability}
                      >
                        {mediaDiscoveryAvailabilityLabel(item.availability)}
                      </span>
                    </header>

                    <p className="media-discovery-overview">
                      {item.overview ?? "No overview is available for this title."}
                    </p>

                    <div className="media-discovery-request-area">
                      <p className="media-discovery-read-only">
                        {item.mediaType === "tv"
                          ? "Open seasons to check request availability for each season."
                          : item.requestEligible
                            ? "Not currently tracked by the media provider."
                            : "This title is already tracked by the media provider."}
                      </p>

                      {item.mediaType === "tv" ? (
                        <TvSeasonSelection
                          canCreateRequests={canCreateRequests}
                          item={item}
                          onLoadTvSeasons={onLoadTvSeasons}
                          onRequestTvSeason={onRequestTvSeason}
                          requestActions={requestActions}
                          seriesState={seriesStates[itemKey]}
                        />
                      ) : !item.requestEligible || !canCreateRequests ? null : (
                        <>
                          <button
                            aria-busy={requestActions[itemKey]?.status === "submitting"}
                            className="media-discovery-primary-button media-discovery-request-button"
                            disabled={requestActions[itemKey] !== undefined}
                            onClick={() => onRequestMovie(item)}
                            type="button"
                          >
                            {requestButtonLabel(requestActions[itemKey], "Request movie")}
                          </button>

                          {requestActions[itemKey] ? (
                            <p aria-live="polite" className="media-discovery-request-message">
                              {requestActions[itemKey]?.message}
                            </p>
                          ) : null}
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
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

  // A mutation target enters this set before the POST begins and remains
  // blocked until the page is remounted. B3.3.1 remains authoritative.
  const blockedRequestKeys = useRef(new Set<string>());

  const [requestActions, setRequestActions] = useState<MediaDiscoveryRequestActions>({});
  const [seriesStates, setSeriesStates] = useState<MediaDiscoverySeriesStates>({});

  const handleLoadTvSeasons = async (item: MediaDiscoveryItem): Promise<void> => {
    if (item.mediaType !== "tv") {
      return;
    }

    const key = mediaRequestKey(item);
    const current = seriesStates[key];

    if (current?.status === "loading" || current?.status === "ready") {
      return;
    }

    setSeriesStates((states) => ({
      ...states,
      [key]: {
        status: "loading"
      }
    }));

    try {
      const detail = await readMediaSeriesDetail({
        providerMediaId: item.providerMediaId
      });

      setSeriesStates((states) => ({
        ...states,
        [key]: {
          status: "ready",
          detail
        }
      }));
    } catch {
      setSeriesStates((states) => ({
        ...states,
        [key]: {
          status: "error",
          message: "Season availability is unavailable. Try again before requesting this title."
        }
      }));
    }
  };

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
          ...(item.year === undefined ? {} : { year: item.year })
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

  const handleRequestTvSeason = async (
    item: MediaDiscoveryItem,
    detail: MediaSeriesDetail,
    season: MediaSeriesSeason
  ): Promise<void> => {
    if (
      item.mediaType !== "tv" ||
      detail.providerMediaId !== item.providerMediaId ||
      !season.requestabilityKnown ||
      !season.requestEligible ||
      !canCreateRequests ||
      !user
    ) {
      return;
    }

    const key = tvSeasonRequestKey(detail, season);

    if (blockedRequestKeys.current.has(key) || requestActions[key] !== undefined) {
      return;
    }

    blockedRequestKeys.current.add(key);

    setRequestActions((current) => ({
      ...current,
      [key]: {
        status: "submitting",
        message: `Submitting ${detail.title} ${season.name} to Atlas…`
      }
    }));

    try {
      await createPersonalMediaRequest(
        {
          mediaType: mediaSeriesRequestType(detail),
          providerMediaId: detail.providerMediaId,
          title: detail.title,
          ...(detail.year === undefined ? {} : { year: detail.year }),
          seasonNumber: season.seasonNumber
        },
        {
          expectedUserId: user.user_id
        }
      );

      setRequestActions((current) => ({
        ...current,
        [key]: {
          status: "submitted",
          message: `${detail.title} ${season.name} was submitted to Atlas.`
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
      onLoadTvSeasons={(item) => {
        void handleLoadTvSeasons(item);
      }}
      onPage={discovery.goToPage}
      onRefresh={discovery.refresh}
      onRequestMovie={(item) => {
        void handleRequestMovie(item);
      }}
      onRequestTvSeason={(item, detail, season) => {
        void handleRequestTvSeason(item, detail, season);
      }}
      onSearch={discovery.search}
      requestActions={requestActions}
      seriesStates={seriesStates}
      state={discovery.state}
    />
  );
}
