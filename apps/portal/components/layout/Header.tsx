import Image from "next/image";
import Link from "next/link";

import { Badge } from "../ui/Badge";
import { Container } from "../ui/Container";

export function Header(): React.ReactElement {
  return (
    <header className="site-header">
      <Container className="site-header__inner">
        <Link className="brand" href="/" aria-label="Project Atlas home">
          <Image src="/atlas-logo.svg" alt="" width={42} height={42} priority />

          <span className="brand__text">
            <span className="brand__name">Project Atlas</span>

            <span className="brand__owner">ShadowInc</span>
          </span>
        </Link>

        <div className="site-header__status">
          <Badge variant="default">v0.9 RC</Badge>

          <Badge variant="success">
            <span className="status-dot" aria-hidden="true" />
            Operational
          </Badge>
        </div>
      </Container>
    </header>
  );
}
