"use client";

import { useEffect, useState } from "react";

import { readAtlasHealth } from "../../lib/services/health";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { Container } from "../ui/Container";

type ApiHealthState =
  | Readonly<{
      phase: "loading";
      label: "Checking";
    }>
  | Readonly<{
      phase: "operational";
      label: "Operational";
      apiVersion: string;
    }>
  | Readonly<{
      phase: "unavailable";
      label: "Unavailable";
    }>;

const platformSystems = [
  ["Media Platform", "Integration pending"],
  ["Automation Engine", "Integration pending"],
  ["Identity Services", "Integration pending"]
] as const;

export function StatusCard(): React.ReactElement {
  const [apiHealth, setApiHealth] = useState<ApiHealthState>({
    phase: "loading",
    label: "Checking"
  });

  useEffect(() => {
    let active = true;

    async function loadHealth(): Promise<void> {
      try {
        const health = await readAtlasHealth();

        if (!active) {
          return;
        }

        setApiHealth({
          phase: "operational",
          label: "Operational",
          apiVersion: health.api_version
        });
      } catch {
        if (!active) {
          return;
        }

        setApiHealth({
          phase: "unavailable",
          label: "Unavailable"
        });
      }
    }

    void loadHealth();

    return () => {
      active = false;
    };
  }, []);

  const apiOperational = apiHealth.phase === "operational";

  return (
    <section id="status" className="status-section">
      <Container>
        <Card className="status-panel">
          <div className="status-panel__summary">
            <Badge variant={apiOperational ? "success" : "default"}>
              {apiOperational ? "Atlas API Operational" : "Atlas API Status Pending"}
            </Badge>

            <h2>
              {apiOperational ? "Atlas is standing by." : "Atlas is checking its connection."}
            </h2>

            <p>
              The Portal now reads the stable Atlas API health contract through the shared typed
              client.
            </p>
          </div>

          <div className="status-list">
            <div className="status-list__item">
              <span>Atlas API</span>

              <span className="status-list__state">
                {apiOperational ? <span className="status-dot" aria-hidden="true" /> : null}

                {apiHealth.label}

                {apiHealth.phase === "operational" ? ` · ${apiHealth.apiVersion}` : ""}
              </span>
            </div>

            {platformSystems.map(([name, status]) => (
              <div className="status-list__item" key={name}>
                <span>{name}</span>
                <span className="status-list__state">{status}</span>
              </div>
            ))}
          </div>
        </Card>
      </Container>
    </section>
  );
}
