import type { Metadata } from "next";

import { RequestsPageClient } from "./RequestsPageClient";

export const metadata: Metadata = {
  title: "Requests",
  description: "Review the lifecycle and availability of your Project Atlas media requests."
};

export default function RequestsPage(): React.ReactElement {
  return <RequestsPageClient />;
}
