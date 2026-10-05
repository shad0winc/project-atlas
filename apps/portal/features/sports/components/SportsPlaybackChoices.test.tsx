// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { SportsPlaybackChoices } from "./SportsPlaybackChoices";

const options = [
  { optionId: "primary", label: "Primary", configured: true },
  { optionId: "backup-1", label: "Backup 1", configured: true },
  { optionId: "backup-2", label: "Backup 2", configured: false },
] as const;

it("shows feeds beside Close, marks the active feed, and prevents duplicate switches", async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement("div"); document.body.append(container);
  const root = createRoot(container);
  let reject!: (error: Error) => void;
  const choose = vi.fn(() => new Promise<void>((_, fail) => { reject = fail; }));
  const close = vi.fn();
  await act(async () => root.render(<SportsPlaybackChoices options={options}
    activeOptionId="primary" onChoose={choose} onCancel={close} />));
  const buttons = container.querySelectorAll("button");
  expect([...buttons].map(button => button.textContent)).toEqual([
    "Close live playback", "Primary", "Backup 1", "Backup 2 — setup pending",
  ]);
  expect(buttons[1].getAttribute("aria-pressed")).toBe("true");
  expect(buttons[1].disabled).toBe(true);
  expect(buttons[3].disabled).toBe(true);
  await act(async () => { buttons[2].click(); buttons[2].click(); });
  expect(choose).toHaveBeenCalledExactlyOnceWith("backup-1");
  expect(buttons[2].disabled).toBe(true);
  // Close stays available while a feed switch is pending.
  expect(buttons[0].disabled).toBe(false);
  await act(async () => buttons[0].click());
  expect(close).toHaveBeenCalledOnce();
  await act(async () => reject(new Error("fixture failure")));
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("busy or unavailable");
  expect(buttons[2].disabled).toBe(false);
  await act(async () => root.render(<SportsPlaybackChoices options={options}
    activeOptionId="backup-1" onChoose={choose} onCancel={close} />));
  expect(buttons[2].getAttribute("aria-pressed")).toBe("true");
  expect(buttons[1].disabled).toBe(false);
  await act(async () => root.unmount()); container.remove();
});

it("blocks switches during automatic startup and supports legacy playback with Close only", async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement("div"); document.body.append(container);
  const root = createRoot(container);
  const choose = vi.fn();
  const close = vi.fn();
  await act(async () => root.render(<SportsPlaybackChoices options={options}
    busy onChoose={choose} onCancel={close} />));
  const buttons = container.querySelectorAll("button");
  expect([...buttons].slice(1).every(button => button.disabled)).toBe(true);
  await act(async () => buttons[2].click());
  expect(choose).not.toHaveBeenCalled();
  await act(async () => root.render(<SportsPlaybackChoices options={[]}
    onChoose={choose} onCancel={close} />));
  expect(container.querySelectorAll("button")).toHaveLength(1);
  await act(async () => root.unmount()); container.remove();
});
