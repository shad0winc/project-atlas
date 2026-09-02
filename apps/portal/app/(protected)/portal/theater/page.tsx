import type { Metadata } from "next";

import { Suspense } from "react";

import { TheaterPageClient } from "./TheaterPageClient";

export const metadata: Metadata = {
  title: "Theater",
  description: "Open resolved Project Atlas media playback."
};

export default function TheaterPage(): React.ReactElement {
  return (
    <Suspense fallback={<p>Preparing playback…</p>}>
      <TheaterPageClient />
    </Suspense>
  );
}
