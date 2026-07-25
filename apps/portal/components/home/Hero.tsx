import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Container } from "../ui/Container";

const capabilities = [
  {
    name: "Identity",
    description: "Secure user profiles, invitations, registration, and media access."
  },
  {
    name: "Automation",
    description: "Scheduled workflows and modular services working quietly in the background."
  },
  {
    name: "Intelligence",
    description: "Retention, policy, favorites, cleanup planning, and system observability."
  }
] as const;

export function Hero(): React.ReactElement {
  return (
    <main>
      <section className="hero">
        <Container className="hero__layout">
          <div className="hero__content">
            <Badge variant="primary">Personal Media Platform</Badge>

            <p className="hero__eyebrow">Simplicity Meets Ingenuity</p>

            <h1>
              Your media.
              <span>Your infrastructure.</span>
              <span>Your Atlas.</span>
            </h1>

            <p className="hero__description">
              A private platform that brings media, users, automation, and operational intelligence
              together under one dependable system.
            </p>

            <div className="hero__actions">
              <Button href="#platform">Explore Atlas</Button>
              <Button href="#status" variant="secondary">
                View System Status
              </Button>
            </div>
          </div>

          <div className="hero__visual" aria-hidden="true">
            <div className="orbital orbital--outer">
              <div className="orbital orbital--middle">
                <div className="orbital orbital--inner">
                  <div className="atlas-core">
                    <span>ATLAS</span>
                    <strong>ONLINE</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Container>
      </section>

      <section id="platform" className="capabilities">
        <Container>
          <div className="section-heading">
            <p className="section-heading__eyebrow">Platform Foundation</p>
            <h2>One system. Three core capabilities.</h2>
            <p>
              Atlas is designed as a modular platform that grows without sacrificing clarity,
              reliability, or control.
            </p>
          </div>

          <div className="capability-grid">
            {capabilities.map((capability, index) => (
              <article className="capability-card" key={capability.name}>
                <span className="capability-card__number">0{index + 1}</span>
                <h3>{capability.name}</h3>
                <p>{capability.description}</p>
              </article>
            ))}
          </div>
        </Container>
      </section>
    </main>
  );
}
