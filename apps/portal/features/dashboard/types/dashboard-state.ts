import type { DashboardSnapshot } from "./dashboard";

export type DashboardErrorState = Readonly<{
  message: string;
}>;

export type DashboardState =
  | Readonly<{
      status: "loading";
      data: null;
      error: null;
    }>
  | Readonly<{
      status: "success";
      data: DashboardSnapshot;
      error: null;
    }>
  | Readonly<{
      status: "error";
      data: null;
      error: DashboardErrorState;
    }>;

export function createDashboardErrorState(error: unknown): DashboardErrorState {
  if (error instanceof Error && error.message.trim()) {
    return {
      message: error.message.trim()
    };
  }

  return {
    message: "Atlas could not load the dashboard."
  };
}

export function createDashboardState(
  data: DashboardSnapshot | null,
  error: DashboardErrorState | null
): DashboardState {
  if (error) {
    return {
      status: "error",
      data: null,
      error
    };
  }

  if (data) {
    return {
      status: "success",
      data,
      error: null
    };
  }

  return {
    status: "loading",
    data: null,
    error: null
  };
}
