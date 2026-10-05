// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";
import { SportsPlaybackChoices } from "./SportsPlaybackChoices";

it("disables unpublished options, prevents duplicate opens, and reports failure", async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement("div"); document.body.append(container);
  const root = createRoot(container);
  let reject!: (error: Error) => void;
  const choose = vi.fn(() => new Promise<void>((_, fail) => { reject = fail; }));
  await act(async () => root.render(<SportsPlaybackChoices options={[
    { optionId: "primary", label: "Primary", configured: true },
    { optionId: "backup-1", label: "Backup 1", configured: false },
  ]} onChoose={choose} onCancel={vi.fn()} />));
  const buttons = container.querySelectorAll("button");
  expect(buttons[1].disabled).toBe(true);
  await act(async () => { buttons[0].click(); buttons[0].click(); });
  expect(choose).toHaveBeenCalledTimes(1);
  expect(buttons[2].disabled).toBe(true);
  await act(async () => reject(new Error("fixture failure")));
  expect(container.querySelector('[role="alert"]')?.textContent).toContain("busy or unavailable");
  expect(buttons[0].disabled).toBe(false);
  await act(async () => root.unmount()); container.remove();
});
