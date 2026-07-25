import { Container } from "./ui/Container";

export function Footer(): React.ReactElement {
  return (
    <footer className="site-footer">
      <Container className="site-footer__inner">
        <div>
          <strong>Project Atlas</strong>
          <span>Built by ShadowInc</span>
        </div>

        <div className="site-footer__meta">
          <span>Version 0.9 RC</span>
          <span aria-hidden="true">•</span>
          <span>Simplicity Meets Ingenuity</span>
        </div>
      </Container>
    </footer>
  );
}
