import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
var apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:5104";
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var buildTarget = process.env.PIN_CONFIGURATOR_BUILD_TARGET || (mode === "extension" ? "extension" : "browser");
    var sourceMapMode = buildTarget === "extension" ? true : "hidden";
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
                    manualChunks: function (id) {
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
