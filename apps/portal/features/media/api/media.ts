import { readMediaSnapshot } from "../services/media";
import type { MediaSnapshot } from "../types/media";

export type LoadMediaOptions = Readonly<{
  signal?: AbortSignal;
}>;

export async function loadMedia({ signal }: LoadMediaOptions = {}): Promise<MediaSnapshot> {
  return readMediaSnapshot({
    signal
  });
}
