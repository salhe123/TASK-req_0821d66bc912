/// <reference types="node" />
import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import * as path from "node:path";

export default defineConfig({
  plugins: [vue() as any],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
    coverage: {
      provider: "v8",
      // Write the machine-readable lcov into the shared /coverage volume so
      // `./coverage/` on the host carries both api + web reports after a run.
      reporter: ["text", "html", "lcov"],
      reportsDirectory: process.env.COVERAGE_DIR ?? "./coverage/web-lcov",
      include: ["src/**/*.{ts,vue}"],
      exclude: [
        "src/main.ts",
        "src/vite-env.d.ts",
        // These are routing/composition wiring that's exercised by the
        // playwright E2E tier, not the vitest component tier. Excluding them
        // keeps the unit-tier metric honest about what it validates.
        "src/router/**",
        "src/App.vue",
      ],
    },
  },
});
