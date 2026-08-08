import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: [
      "components/**/*.test.ts",
      "components/**/*.test.tsx",
      "features/**/*.test.ts",
      "features/**/*.test.tsx",
      "lib/**/*.test.ts",
      "lib/**/*.test.tsx"
    ],
    clearMocks: true,
    restoreMocks: true
  }
});
