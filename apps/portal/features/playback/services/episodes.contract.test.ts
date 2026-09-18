import { describe, expect, it, vi } from "vitest";

const { authenticatedRequestMock } = vi.hoisted(() => ({
  authenticatedRequestMock: vi.fn()
}));

vi.mock(
  "../../../lib/services/authenticated",
  () => ({
    authenticatedAtlasApiRequest:
      authenticatedRequestMock
  })
);

import * as sessionServices from "./session";

describe(
  "series episode navigation transport",
  () => {
    it(
      "loads normalized browser-safe episode identities",
      async () => {
        authenticatedRequestMock.mockResolvedValue({
          provider: "jellyfin",
          series_id: "series-1",
          episodes: [
            {
              id: "episode-s01e01",
              title: "Pilot",
              series_name: "Example Series",
              season_number: 1,
              episode_number: 1
            },
            {
              id: "episode-s02e03",
              title: "Return",
              series_name: "Example Series",
              season_number: 2,
              episode_number: 3
            }
          ]
        });

        const sessionModule =
          sessionServices as unknown as {
            resolveSeriesEpisodes?: (
              provider: string,
              itemId: string,
              signal?: AbortSignal
            ) => Promise<
              readonly {
                id: string;
                title: string;
                seriesName?: string;
                seasonNumber?: number;
                episodeNumber?: number;
              }[]
            >;
          };

        expect(
          sessionModule.resolveSeriesEpisodes
        ).toBeTypeOf("function");

        const episodes =
          await sessionModule.resolveSeriesEpisodes!(
            " Jellyfin ",
            " series-1 "
          );

        expect(
          authenticatedRequestMock
        ).toHaveBeenCalledWith(
          "/media/playback/jellyfin/series-1/episodes",
          {
            method: "GET",
            cache: "no-store",
            signal: undefined
          }
        );

        expect(episodes).toEqual([
          {
            id: "episode-s01e01",
            title: "Pilot",
            seriesName: "Example Series",
            seasonNumber: 1,
            episodeNumber: 1
          },
          {
            id: "episode-s02e03",
            title: "Return",
            seriesName: "Example Series",
            seasonNumber: 2,
            episodeNumber: 3
          }
        ]);
      }
    );
  }
);
