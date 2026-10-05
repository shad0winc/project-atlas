"use client";
import { useRef, useState } from "react";
import type { SportsPlaybackOption } from "../services/playbackOptions";

export function SportsPlaybackChoices({ options, onChoose, onCancel }: Readonly<{
  options: readonly SportsPlaybackOption[];
  onChoose: (optionId: string) => Promise<void>;
  onCancel: () => void;
}>): React.ReactElement {
  const lock = useRef(false);
  const [opening, setOpening] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function choose(optionId: string): Promise<void> {
    if (lock.current) return;
    lock.current = true;
    setOpening(optionId);
    setError(null);
    try { await onChoose(optionId); }
    catch { setError("Playback could not start. The feed may be busy or unavailable."); }
    finally { lock.current = false; setOpening(null); }
  }
  return <section className="requests-message-panel" aria-labelledby="sports-playback-choices">
    <h2 id="sports-playback-choices">Choose a playback feed</h2>
    <p>Choose an alternative if a feed has playback problems. Switching closes your current playback first.</p>
    {error ? <p role="alert">{error}</p> : null}
    {options.map(option => <button key={option.optionId} type="button" disabled={!option.configured || opening !== null}
      onClick={() => { void choose(option.optionId); }}>
      {opening === option.optionId ? "Opening…" : option.label}{!option.configured ? " — setup pending" : ""}
    </button>)}
    <button type="button" disabled={opening !== null} onClick={onCancel}>Cancel</button>
  </section>;
}
