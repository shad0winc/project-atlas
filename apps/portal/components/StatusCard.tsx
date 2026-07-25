import { Badge } from "./ui/Badge";
import { Card } from "./ui/Card";
import { Container } from "./ui/Container";

const systems = [
  ["Atlas API", "Operational"],
  ["Media Platform", "Operational"],
  ["Automation Engine", "Operational"],
  ["Identity Services", "Operational"]
] as const;

export function StatusCard(): React.ReactElement {
  return (
    <section id="status" className="status-section">
      <Container>
        <Card className="status-panel">
          <div className="status-panel__summary">
            <Badge variant="success">All Systems Operational</Badge>

            <h2>Atlas is standing by.</h2>

            <p>
              The portal foundation is online and ready to become the primary
              interface for the Atlas platform.
            </p>
          </div>

          <div className="status-list">
            {systems.map(([name, status]) => (
              <div className="status-list__item" key={name}>
                <span>{name}</span>

                <span className="status-list__state">
                  <span className="status-dot" aria-hidden="true" />
                  {status}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </Container>
    </section>
  );
}
