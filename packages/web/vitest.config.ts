import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

// Unit tests for pure modules (no DOM). The `@/` alias mirrors tsconfig paths.
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
    // Single forked process — avoids worker-pool crashes on constrained hosts
    // and keeps runs deterministic (these are fast pure-unit tests).
    pool: "forks",
    poolOptions: { forks: { singleFork: true } },
  },
});
