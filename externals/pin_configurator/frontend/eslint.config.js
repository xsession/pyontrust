import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["dist", "coverage"],
  },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommendedTypeChecked],
    files: ["src/**/*.{ts,tsx}", "vite.config.ts"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        project: ["./tsconfig.json", "./tsconfig.node.json"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.name='fetch']",
          message: "Use the typed transport boundary in src/services/http.ts instead of calling fetch directly.",
        },
      ],
    },
  },
  {
    files: ["src/services/http.ts"],
    rules: {
      "no-restricted-syntax": "off",
    },
  },
  {
    files: ["src/views/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["../project", "../project/*", "../services", "../services/*", "../store", "../store/*"],
              message: "Views must receive derived data and actions through presenter-owned view models instead of importing project, service, or store modules directly.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/{app,shared,workspace}/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["../services", "../services/*", "../store", "../store/*"],
              message: "Only presenters and project/controller modules may talk directly to service or store modules.",
            },
          ],
        },
      ],
    },
  },
);