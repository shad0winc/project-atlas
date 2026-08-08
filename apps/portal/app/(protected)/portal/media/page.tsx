import type { Metadata } from "next";

import { MediaPageClient } from "./MediaPageClient";

export const metadata: Metadata = {
  title: "Media",
  description: "Review Project Atlas media libraries and collection statistics."
};

export default function MediaPage(): React.ReactElement {
  return <MediaPageClient />;
}
