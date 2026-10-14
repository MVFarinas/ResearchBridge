// Adds jest-dom matchers (toBeInTheDocument, toHaveAttribute, ...) and cleans up after each test.
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
