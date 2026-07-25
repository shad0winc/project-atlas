import type { ReactNode } from "react";

type ContainerProps = Readonly<{
  children: ReactNode;
  className?: string;
}>;

export function Container({
  children,
  className = ""
}: ContainerProps): React.ReactElement {
  const classes = ["container", className].filter(Boolean).join(" ");

  return <div className={classes}>{children}</div>;
}
