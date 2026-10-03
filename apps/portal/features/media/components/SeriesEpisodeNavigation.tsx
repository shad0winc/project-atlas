"use client";

import Link from "next/link";
import { sourceQuality } from "../types/quality";
import {
  useMemo,
  useState
} from "react";

import {
  resolveSeriesEpisodes,
  type SeriesEpisode
} from "../../playback/services/session";

type SeriesEpisodeNavigationProps = Readonly<{
  provider: string;
  seriesId: string;
  title: string;
  currentEpisodeId?: string;
}>;

type NavigationStatus =
  | "idle"
  | "loading"
  | "ready"
  | "error";

type SeasonKey =
  | number
  | "other";

function episodeSeasonKey(
  episode: SeriesEpisode
): SeasonKey {
  return typeof episode.seasonNumber === "number"
    ? episode.seasonNumber
    : "other";
}

function seasonLabel(
  season: SeasonKey
): string {
  if (season === "other") {
    return "Other";
  }

  return season === 0
    ? "Specials"
    : `Season ${season}`;
}

function episodeLabel(
  episode: SeriesEpisode
): string {
  const parts: string[] = [];

  if (
    typeof episode.seasonNumber ===
    "number"
  ) {
    parts.push(
      `S${episode.seasonNumber}`
    );
  }

  if (
    typeof episode.episodeNumber ===
    "number"
  ) {
    parts.push(
      `E${episode.episodeNumber}`
    );
  }

  parts.push(episode.title, "—", sourceQuality(episode.videoWidth, episode.videoHeight));

  return parts.join(" ");
}

export function SeriesEpisodeNavigation({
  provider,
  seriesId,
  title,
  currentEpisodeId
}: SeriesEpisodeNavigationProps): React.ReactElement {
  const [status, setStatus] =
    useState<NavigationStatus>("idle");

  const [episodes, setEpisodes] =
    useState<readonly SeriesEpisode[]>([]);

  const [error, setError] =
    useState<string | null>(null);

  const [selectedSeason, setSelectedSeason] =
    useState<SeasonKey | null>(null);

  const [selectedEpisodeId, setSelectedEpisodeId] =
    useState<string>("");

  const seasons = useMemo(
    (): readonly SeasonKey[] => {
      const numberedSeasons =
        Array.from(
          new Set(
            episodes.flatMap(
              (episode) =>
                typeof episode.seasonNumber ===
                "number"
                  ? [
                      episode.seasonNumber
                    ]
                  : []
            )
          )
        ).sort(
          (left, right) =>
            left - right
        );

      const hasOther =
        episodes.some(
          (episode) =>
            typeof episode.seasonNumber !==
            "number"
        );

      return hasOther
        ? [
            ...numberedSeasons,
            "other"
          ]
        : numberedSeasons;
    },
    [episodes]
  );

  const visibleEpisodes = useMemo(
    () =>
      selectedSeason === null
        ? []
        : episodes.filter(
            (episode) =>
              episodeSeasonKey(
                episode
              ) === selectedSeason
          ),
    [
      episodes,
      selectedSeason
    ]
  );

  async function load(): Promise<void> {
    setStatus("loading");
    setError(null);

    try {
      const loaded =
        await resolveSeriesEpisodes(
          provider,
          seriesId
        );

      setEpisodes(loaded);

      const current = loaded.find((episode) => episode.id === currentEpisodeId);
      const firstSeason =
        loaded.length === 0
          ? null
          : episodeSeasonKey(
              current ?? loaded[0]
            );

      setSelectedSeason(firstSeason);

      const firstEpisode =
        firstSeason === null
          ? undefined
          : loaded.find(
              (episode) =>
                episodeSeasonKey(
                  episode
                ) === firstSeason
            );

      setSelectedEpisodeId(
        current?.id ?? firstEpisode?.id ?? ""
      );

      setStatus("ready");
    } catch {
      setEpisodes([]);
      setSelectedSeason(null);
      setSelectedEpisodeId("");
      setError(
        "Episodes are unavailable."
      );
      setStatus("error");
    }
  }

  if (status === "idle") {
    return (
      <button
        className="media-discovery-primary-button"
        onClick={() => {
          void load();
        }}
        type="button"
      >
        View episodes
      </button>
    );
  }

  if (status === "loading") {
    return (
      <p
        aria-live="polite"
        className="media-discovery-message"
      >
        Loading episodes…
      </p>
    );
  }

  if (status === "error") {
    return (
      <div
        className="media-discovery-message"
        role="alert"
      >
        <p>
          {error ??
            "Episodes are unavailable."}
        </p>

        <button
          className="media-discovery-secondary-button"
          onClick={() => {
            void load();
          }}
          type="button"
        >
          Retry episodes
        </button>
      </div>
    );
  }

  if (
    seasons.length === 0 ||
    selectedSeason === null
  ) {
    return (
      <p className="media-discovery-message">
        No playable episodes are available
        for {title}.
      </p>
    );
  }

  return (
    <div
      aria-label={`${title} episode navigation`}
      className="media-discovery-message"
    >
      <label>
        Season
        <select
          aria-label={`Season for ${title}`}
          onChange={(event) => {
            const rawSeason =
              event.target.value;

            const season: SeasonKey =
              rawSeason === "other"
                ? "other"
                : Number(rawSeason);

            setSelectedSeason(season);

            const firstEpisode =
              episodes.find(
                (episode) =>
                  episodeSeasonKey(
                    episode
                  ) === season
              );

            setSelectedEpisodeId(
              firstEpisode?.id ?? ""
            );
          }}
          value={selectedSeason}
        >
          {seasons.map(
            (season) => (
              <option
                key={String(season)}
                value={season}
              >
                {seasonLabel(
                  season
                )}
              </option>
            )
          )}
        </select>
      </label>

      <label>
        Episode
        <select
          aria-label={`Episode for ${title}`}
          onChange={(event) => {
            setSelectedEpisodeId(
              event.target.value
            );
          }}
          value={selectedEpisodeId}
        >
          {visibleEpisodes.map(
            (episode) => (
              <option
                key={episode.id}
                value={episode.id}
              >
                {episodeLabel(
                  episode
                )}
              </option>
            )
          )}
        </select>
      </label>

      <p aria-live="polite">
        {sourceQuality(episodes.find(row => row.id === selectedEpisodeId)?.videoWidth,
          episodes.find(row => row.id === selectedEpisodeId)?.videoHeight)}
      </p>

      {selectedEpisodeId ? (
        <Link
          className="media-discovery-primary-button"
          href={`/portal/theater?provider=${encodeURIComponent(
            provider.trim().toLowerCase()
          )}&item=${encodeURIComponent(
            selectedEpisodeId
          )}`}
        >
          Watch episode
        </Link>
      ) : null}
    </div>
  );
}
