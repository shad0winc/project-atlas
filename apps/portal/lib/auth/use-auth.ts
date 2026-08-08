"use client";

import { useContext } from "react";

import { AtlasAuthContext } from "./context";
import type { AtlasAuthContextValue } from "./types";

/**
 * Read the active Atlas authentication context.
 */
export function useAuth(): AtlasAuthContextValue {
  const context = useContext(AtlasAuthContext);

  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider.");
  }

  return context;
}
