import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Project Atlas",
    template: "%s | Project Atlas"
  },
  description:
    "Project Atlas is a private media, automation, and intelligence platform by ShadowInc.",
  applicationName: "Project Atlas"
};

type RootLayoutProps = Readonly<{
  children: ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProps): React.ReactElement {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
