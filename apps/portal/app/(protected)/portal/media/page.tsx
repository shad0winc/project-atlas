import type { Metadata } from "next";

import { MediaPageClient } from "./MediaPageClient";

export const metadata: Metadata = {
  title: "Media",
  description: "Browse and search movies and TV shows through Project Atlas."
};

export default function MediaPage(): React.ReactElement {
  return <MediaPageClient />;
}
