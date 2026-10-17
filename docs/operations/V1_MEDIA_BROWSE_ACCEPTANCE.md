# Media browse acceptance queued after Sports

User requirements confirmed 2026-10-17. These are 1.0 acceptance work, queued
after the current Sports section; this document does not implement them.

- Identify the exact requested title with source-matched poster/backdrop artwork
  when available. Preserve title/year/edition context and a clear fallback when
  artwork is absent. Do not substitute unrelated promotional images.
- Show original/native language and available dub/subtitle languages using
  reliable source/release evidence. Distinguish unknown from unavailable.
- Show media quality with enough context to distinguish a source offering from
  a selected/requested release and an actually acquired file.
- Separate untracked media from already requested or tracked media. Requested
  and processing items must expose the same status/progress component and
  meanings used by the Library category.
- Keep transitions consistent through request, acquisition, processing and
  Library availability. Respect existing user/household visibility and request
  deduplication rules. Reuse established status contracts instead of creating
  competing progress estimates.

Before implementation inspect the current Media browse, source response fields,
Library status component and relevant request permissions. Verify exact title
matching, missing artwork, multiple language/release options, unknown metadata,
existing requests, processing failures and completed items. No new provider
scraping, guessed language availability or fabricated quality is implied.
