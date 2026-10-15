"use client";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../../../lib/auth/use-auth";
import { loadSportsSessionObservation, type SportsSessionObservation } from "../api/sports-sessions";

type State = Readonly<{status: "loading"}> | Readonly<{status: "error"}> |
  Readonly<{status: "ready"; report: SportsSessionObservation}>;
export function useSportsSessionObservation(enabled: boolean) {
  const { isAuthenticated } = useAuth();
  const [state, setState] = useState<State>({status: "loading"});
  const [version, setVersion] = useState(0);
  const refresh = useCallback(() => { setState({status: "loading"}); setVersion(v => v + 1); }, []);
  useEffect(() => {
    if (!enabled || !isAuthenticated) return;
    const controller = new AbortController();
    loadSportsSessionObservation(controller.signal).then(report => {
      if (!controller.signal.aborted) setState({status: "ready", report});
    }).catch(() => {
      if (!controller.signal.aborted) setState({status: "error"});
    });
    return () => controller.abort();
  }, [enabled, isAuthenticated, version]);
  return { state, refresh };
}
