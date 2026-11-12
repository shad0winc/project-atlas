import type { MediaSeriesDetail } from "../types/series";

export function SeriesAiringNotice({ detail }: { detail: MediaSeriesDetail }) {
  if (!detail.isOngoing) return null;

  const nextSeason = detail.seasons.find(season => season.nextEpisodeAirDate !== undefined);
  const nextEpisodeAirDate = nextSeason?.nextEpisodeAirDate;

  return (
    <>
      {nextSeason && nextEpisodeAirDate ? (
        <p className="media-discovery-request-message">
          Next episode ({nextSeason.name}) airs{" "}
          <time dateTime={nextEpisodeAirDate}>
            {new Intl.DateTimeFormat(undefined, { dateStyle: "long", timeZone: "UTC" })
              .format(new Date(`${nextEpisodeAirDate}T00:00:00Z`))}
          </time>
          .
        </p>
      ) : (
        <p className="media-discovery-request-message">Next episode air date is unavailable.</p>
      )}
      <p className="media-discovery-request-message">
        For monitored seasons, episodes are expected within 24 hours of airing when an eligible release is available.
      </p>
    </>
  );
}
