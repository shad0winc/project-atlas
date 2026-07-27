import type { MediaSummary as MediaSummaryModel } from "../types/media";

type MediaSummaryProps = Readonly<{
  summary: MediaSummaryModel;
}>;

type SummaryItem = Readonly<{
  label: string;
  value: number;
}>;

export function MediaSummary({ summary }: MediaSummaryProps): React.ReactElement {
  const items: readonly SummaryItem[] = [
    {
      label: "Configured libraries",
      value: summary.libraryCount
    },
    {
      label: "Available libraries",
      value: summary.availableLibraryCount
    },
    {
      label: "Unavailable libraries",
      value: summary.unavailableLibraryCount
    },
    {
      label: "Represented items",
      value: summary.totalItemCount
    }
  ];

  return (
    <section aria-label="Media library summary" className="media-summary-grid">
      {items.map((item) => (
        <article className="media-summary-card" key={item.label}>
          <span>{item.label}</span>
          <strong>{item.value.toLocaleString("en-US")}</strong>
        </article>
      ))}
    </section>
  );
}
