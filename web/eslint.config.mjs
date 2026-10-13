/**
 * ESLint flat config: Next.js core-web-vitals and TypeScript rules, plus
 * eslint-plugin-jsdoc to require TSDoc comments on every exported function,
 * component, hook and type (docs/conventions.md).
 */
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
import jsdoc from "eslint-plugin-jsdoc";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  jsdoc.configs["flat/recommended-typescript-error"],
  {
    files: ["**/*.{ts,tsx,mts}"],
    settings: { jsdoc: { mode: "typescript" } },
    rules: {
      // Every exported function, component, hook, class and type has a doc comment.
      "jsdoc/require-jsdoc": [
        "error",
        {
          publicOnly: true,
          require: {
            FunctionDeclaration: true,
            ArrowFunctionExpression: true,
            FunctionExpression: true,
            ClassDeclaration: true,
            MethodDefinition: true,
          },
          contexts: ["TSInterfaceDeclaration", "TSTypeAliasDeclaration", "TSEnumDeclaration"],
        },
      ],
      // Destructured React props are documented on their Props type instead.
      "jsdoc/require-param": ["error", { checkDestructuredRoots: false }],
      // TSDoc uses "@param name - description".
      "jsdoc/require-hyphen-before-param-description": ["error", "always"],
      "jsdoc/tag-lines": ["error", "any", { startLines: 1 }],
    },
  },
  {
    // Tests are documented by their names and a one-line comment where useful.
    files: ["**/*.test.{ts,tsx}", "vitest.setup.ts"],
    rules: { "jsdoc/require-jsdoc": "off" },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "coverage/**"]),
]);
