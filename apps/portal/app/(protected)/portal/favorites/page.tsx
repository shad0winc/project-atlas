import type { Metadata } from "next";

import { FavoritesPageClient } from "./FavoritesPageClient";

export const metadata: Metadata = {
  title: "Favorites",
  description: "Review and manage media saved to your Project Atlas Favorites list."
};

export default function FavoritesPage(): React.ReactElement {
  return <FavoritesPageClient />;
}
