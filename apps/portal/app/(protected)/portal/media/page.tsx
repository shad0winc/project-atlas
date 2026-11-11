import type { Metadata } from "next";

import { MediaPageClient } from "./MediaPageClient";

export const metadata: Metadata = {
  title: "Media",
  description: "Browse and search movies and TV shows through Project Atlas."
};

export default async function MediaPage({
  searchParams
}: { searchParams: Promise<{ view?: string | string[] }> }): Promise<React.ReactElement> {
  const { view } = await searchParams;
  return <MediaPageClient library={view === "library"} />;
}
