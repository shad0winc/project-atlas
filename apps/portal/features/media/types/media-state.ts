import type { MediaSnapshot } from "./media";

export type MediaLoadingState = Readonly<{
  status: "loading";
}>;

export type MediaReadyState = Readonly<{
  status: "ready";
  data: MediaSnapshot;
}>;

export type MediaErrorState = Readonly<{
  status: "error";
  error: Error;
}>;

export type MediaState = MediaLoadingState | MediaReadyState | MediaErrorState;

export function createMediaState(data: MediaSnapshot | null, error: Error | null): MediaState {
  if (error) {
    return {
      status: "error",
      error
    };
  }

  if (data) {
    return {
      status: "ready",
      data
    };
  }

  return {
    status: "loading"
  };
}
