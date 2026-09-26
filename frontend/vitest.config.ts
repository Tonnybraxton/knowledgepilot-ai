import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
export default defineConfig({ plugins: [react()], resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } }, test: { environment: "jsdom", setupFiles: ["./tests/setup.ts"], exclude: ["node_modules/**", "tests/e2e/**", ".next/**"] } });
