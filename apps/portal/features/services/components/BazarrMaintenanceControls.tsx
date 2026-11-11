"use client";

import { useEffect, useRef, useState } from "react";

import { Card } from "../../../components/ui/Card";
import {
  loadServiceMaintenance,
  startServiceMaintenance,
  waitForServicePoll,
  type ServiceMaintenanceState
} from "../api/services";

export function BazarrMaintenanceControls({
  onCompleted
}: Readonly<{ onCompleted: () => void }>): React.ReactElement {
  const [state, setState] = useState<ServiceMaintenanceState | null>(null);
  const [error, setError] = useState(false);
  const [confirmRollback, setConfirmRollback] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const action = useRef<AbortController | null>(null);
  const requestedJob = useRef<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let observedRunningJob = requestedJob.current;
    async function observe(): Promise<void> {
      try {
        while (!controller.signal.aborted) {
          const next = await loadServiceMaintenance(controller.signal);
          if (controller.signal.aborted) {
            return;
          }
          setState(next);
          setError(false);
          const running = next.job?.status === "queued" || next.job?.status === "running";
          if (!running) {
            if (next.job?.id === observedRunningJob && next.job?.status === "completed") {
              requestedJob.current = null;
              onCompleted();
            }
            return;
          }
          observedRunningJob = next.job?.id ?? null;
          await waitForServicePoll(controller.signal);
        }
      } catch {
        if (!controller.signal.aborted) {
          setError(true);
        }
      }
    }
    void observe();
    return () => controller.abort();
  }, [version, onCompleted]);

  useEffect(() => () => action.current?.abort(), []);

  async function submit(operation: "bazarr.apply" | "bazarr.rollback"): Promise<void> {
    if (action.current) {
      return;
    }
    const controller = new AbortController();
    action.current = controller;
    setSubmitting(true);
    setError(false);
    try {
      const job = await startServiceMaintenance(operation, controller.signal);
      if (!controller.signal.aborted) {
        requestedJob.current = job.id;
        setState((current) => current ? { ...current, job } : current);
        setConfirmRollback(false);
        setVersion((current) => current + 1);
      }
    } catch {
      if (!controller.signal.aborted) {
        setError(true);
      }
    } finally {
      action.current = null;
      if (!controller.signal.aborted) {
        setSubmitting(false);
      }
    }
  }

  const busy = submitting || state?.job?.status === "queued" || state?.job?.status === "running";
  return (
    <Card>
      <h3>Bazarr maintenance</h3>
      {state ? <p>Reviewed operation status {state.bazarr.status}</p> : <p>Loading maintenance status…</p>}
      {state?.bazarr.version_label ? <p>Installed build {state.bazarr.version_label}</p> : null}
      {state && !state.bazarr.maintenance_enabled ? (
        <p>Enable maintenance mode before changing services.</p>
      ) : null}
      <div role="status" aria-live="polite">
        {busy ? <p>{state?.job?.progress || "Starting operation…"}</p> : null}
        {state?.job?.status === "failed" ? <p>The host operation stopped. Review its status before retrying.</p> : null}
        {error ? <p>Service maintenance is unavailable. Try refreshing its status.</p> : null}
      </div>
      {state?.bazarr.can_apply ? (
        <button className="dashboard-retry-button" type="button" disabled={busy}
          onClick={() => void submit("bazarr.apply")}>
          Apply reviewed update
        </button>
      ) : null}
      {state?.bazarr.can_rollback && !confirmRollback ? (
        <button className="dashboard-retry-button" type="button" disabled={busy}
          onClick={() => setConfirmRollback(true)}>
          Review rollback
        </button>
      ) : null}
      {confirmRollback ? (
        <div>
          <p>Restore the previous container, configuration, and database saved before the update.
            The replaced configuration will be retained separately.</p>
          <button className="dashboard-retry-button" type="button" disabled={busy}
            onClick={() => void submit("bazarr.rollback")}>
            Restore previous build and database
          </button>
          <button className="dashboard-retry-button" type="button" disabled={busy}
            onClick={() => setConfirmRollback(false)}>
            Cancel
          </button>
        </div>
      ) : null}
      <button className="dashboard-retry-button" type="button" disabled={busy}
        onClick={() => setVersion((current) => current + 1)}>
        Refresh maintenance status
      </button>
    </Card>
  );
}
