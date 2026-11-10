"use client";

import { useEffect, useRef, useState } from "react";

import { loadBazarrUpdatePlan, type BazarrUpdatePlan } from "../api/services";

type PreviewState =
  { status: "idle" | "loading" | "error" } | { status: "ready"; plan: BazarrUpdatePlan };

export function BazarrUpdatePreview(): React.ReactElement {
  const [state, setState] = useState<PreviewState>({ status: "idle" });
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);

  async function preview(): Promise<void> {
    if (request.current) {
      return;
    }

    const controller = new AbortController();
    request.current = controller;
    setState({ status: "loading" });
    try {
      const plan = await loadBazarrUpdatePlan(controller.signal);
      if (!controller.signal.aborted) {
        setState({ status: "ready", plan });
      }
    } catch {
      if (!controller.signal.aborted) {
        setState({ status: "error" });
      }
    } finally {
      request.current = null;
    }
  }

  return (
    <>
      <button
        className="dashboard-retry-button"
        disabled={state.status === "loading"}
        onClick={() => void preview()}
        type="button"
      >
        Preview update
      </button>
      <div role="status">
        {state.status === "loading" ? <p>Preparing the update preview…</p> : null}
        {state.status === "error" ? (
          <p>Could not preview this update. Check for updates and try again.</p>
        ) : null}
        {state.status === "ready" ? (
          <>
            <h4>Dry-run update plan</h4>
            <dl style={{ overflowWrap: "anywhere" }}>
              <dt>Current image for rollback</dt>
              <dd>{state.plan.current_image.canonical_reference}</dd>
              <dt>Target image</dt>
              <dd>{state.plan.target_image.canonical_reference}</dd>
            </dl>
            <ul>
              {state.plan.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </>
        ) : null}
      </div>
    </>
  );
}
