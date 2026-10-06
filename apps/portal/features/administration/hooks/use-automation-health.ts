"use client";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../../lib/auth/use-auth";
import { loadAutomationHealth, type AutomationHealth } from "../api/automation-health";

export type AutomationHealthState =
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "error" }>
  | Readonly<{ status: "ready"; report: AutomationHealth }>;

export function useAutomationHealth(enabled: boolean) {
  const { isAuthenticated } = useAuth();
  const [state, setState] = useState<AutomationHealthState>({ status: "loading" });
  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => {
    setState({ status: "loading" });
    setVersion((value) => value + 1);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    if (enabled && isAuthenticated) {
      loadAutomationHealth(controller.signal).then((report) => {
        if (!controller.signal.aborted) setState({ status: "ready", report });
      }).catch(() => {
        if (!controller.signal.aborted) setState({ status: "error" });
      });
    }
    return () => controller.abort();
  }, [enabled, isAuthenticated, version]);
  return { state, refresh };
}
