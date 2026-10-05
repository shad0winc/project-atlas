"use client";
import { useRef, useState } from "react";
import type { SportsPlaybackOption } from "../services/playbackOptions";

export function SportsPlaybackChoices({ options, activeOptionId, busy = false, onChoose, onCancel }: Readonly<{
  options: readonly SportsPlaybackOption[];
  activeOptionId?: string;
  busy?: boolean;
  onChoose: (optionId: string) => Promise<void>;
  onCancel: () => void;
}>): React.ReactElement {
  const lock = useRef(false);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function choose(optionId: string): Promise<void> {
    if (lock.current || busy || optionId === activeOptionId) return;
    lock.current = true;
    setOpening(optionId);
    setError(null);
    try { await onChoose(optionId); }
    catch { setError("Playback could not start. The feed may be busy or unavailable."); }
    finally { lock.current = false; setOpening(null); }
  }
  return <div>
    <div className="requests-toolbar" role="group" aria-label="Live playback controls">
      <button type="button" className="requests-refresh-button" aria-label="Close live playback" onClick={onCancel}>
        Close live playback
      </button>
      {options.map(option => <button key={option.optionId} type="button"
        className="requests-refresh-button" aria-pressed={option.optionId === activeOptionId}
        disabled={!option.configured || busy || opening !== null || option.optionId === activeOptionId}
        onClick={() => { void choose(option.optionId); }}>
        {opening === option.optionId ? "Opening…" : option.label}{!option.configured ? " — setup pending" : ""}
      </button>)}
    </div>
    {error ? <p role="alert">{error}</p> : null}
  </div>;
}
