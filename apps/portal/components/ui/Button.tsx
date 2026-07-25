import type { ReactNode } from "react";

type ButtonProps = Readonly<{
  children: ReactNode;
  href: string;
  variant?: "primary" | "secondary";
}>;

export function Button({
  children,
  href,
  variant = "primary"
}: ButtonProps): React.ReactElement {
  return (
    <a className={`button button--${variant}`} href={href}>
      {children}
    </a>
  );
}
