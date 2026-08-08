import type { ReactNode } from "react";

type CardProps = Readonly<{
  children: ReactNode;
  className?: string;
}>;

export function Card({ children, className = "" }: CardProps): React.ReactElement {
  const classes = ["card", className].filter(Boolean).join(" ");

  return <section className={classes}>{children}</section>;
}
