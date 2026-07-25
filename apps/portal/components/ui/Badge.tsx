import type { ReactNode } from "react";

type BadgeVariant = "default" | "success" | "primary";

type BadgeProps = Readonly<{
  children: ReactNode;
  variant?: BadgeVariant;
}>;

export function Badge({ children, variant = "default" }: BadgeProps): React.ReactElement {
  return <span className={`badge badge--${variant}`}>{children}</span>;
}
