import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:5104";

export default defineConfig(({ mode }) => {
  const buildTarget = process.env.PIN_CONFIGURATOR_BUILD_TARGET || (mode === "extension" ? "extension" : "browser");
  const sourceMapMode = buildTarget === "extension" ? true : "hidden";

  return {
    plugins: [react()],
    base: "/app/",
    build: {
      outDir: "dist",
      assetsDir: "assets",
      emptyOutDir: true,
      cssCodeSplit: true,
      assetsInlineLimit: 0,
      sourcemap: sourceMapMode,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes("node_modules")) {
              return undefined;
            }

            if (id.includes("monaco-editor") || id.includes("@monaco-editor/react")) {
              return "monaco";
            }

            if (id.includes("dockview")) {
              return "dockview";
            }

            if (id.includes("@radix-ui")) {
              return "radix";
            }

            if (id.includes("@tanstack/react-virtual")) {
              return "virtualization";
            }

            return "vendor";
          },
        },
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          api: "modern-compiler",
        },
      },
    },
    server: {
      port: 4173,
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: "./src/testing/setupTests.ts",
    },
  };
});