import fs from "node:fs";

import {
  describe,
  expect,
  it
} from "vitest";

const componentUrl = new URL(
  "./SeriesEpisodeNavigation.tsx",
  import.meta.url
);

describe(
  "SeriesEpisodeNavigation product contract",
  () => {
    it(
      "provides the explicit series episode navigation component",
      () => {
        expect(
          fs.existsSync(componentUrl)
        ).toBe(true);
      }
    );

    it(
      "defines season-aware episode presentation and exact Theater routing",
      () => {
        expect(
          fs.existsSync(componentUrl)
        ).toBe(true);

        const source = fs.readFileSync(
          componentUrl,
          "utf8"
        );

        expect(source).toContain(
          "SeriesEpisodeNavigation"
        );

        expect(source).toMatch(
          /selectedSeason/
        );

        expect(source).toMatch(
          /seasonNumber/
        );

        expect(source).toMatch(
          /episodeNumber/
        );

        expect(source).toContain(
          "/portal/theater"
        );

        expect(source).toMatch(
          /episode\.id/
        );
      }
    );

    it(
      "provides explicit loading and error presentation",
      () => {
        expect(
          fs.existsSync(componentUrl)
        ).toBe(true);

        const source = fs.readFileSync(
          componentUrl,
          "utf8"
        );

        expect(source).toMatch(
          /loading/
        );

        expect(source).toMatch(
          /error/
        );
      }
    );
  }
);

describe(
  "SeriesEpisodeNavigation incomplete Jellyfin metadata hardening",
  () => {
    it(
      "keeps episodes without season metadata navigable",
      () => {
        const source = fs.readFileSync(
          componentUrl,
          "utf8"
        );

        expect(source).toContain(
          '"Other"'
        );

        expect(source).not.toMatch(
          /\.filter\(\s*\(\s*value\s*\)[\s\S]*typeof value === "number"/
        );
      }
    );

    it(
      "does not invent season or episode zero labels for missing metadata",
      () => {
        const source = fs.readFileSync(
          componentUrl,
          "utf8"
        );

        expect(source).not.toContain(
          "episode.seasonNumber ?? 0"
        );

        expect(source).not.toContain(
          "episode.episodeNumber ?? 0"
        );
      }
    );

    it(
      "retains exact episode identity when metadata is incomplete",
      () => {
        const source = fs.readFileSync(
          componentUrl,
          "utf8"
        );

        expect(source).toMatch(
          /episode\.id/
        );

        expect(source).toContain(
          "/portal/theater"
        );
      }
    );
  }
);
