import type { Metadata } from "next";

import { LibraryPageClient } from "./LibraryPageClient";

export const metadata: Metadata = {
  title: "Library",
  description: "Watch available Project Atlas media and review your request lifecycle."
};

export default function LibraryPage(): React.ReactElement {
  return <LibraryPageClient />;
}
