import type { Metadata } from "next";

import { SportsPageClient } from "./SportsPageClient";

export const metadata: Metadata = {
  title: "Sports",
  description: "Browse and request supported sporting events through Project Atlas."
};

export default function SportsPage(): React.ReactElement {
  return <SportsPageClient />;
}
