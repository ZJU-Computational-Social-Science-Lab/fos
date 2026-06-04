/*
This file checks that the app builder knows what "@/" means.
The test makes sure the Vite config points "@" at the frontend folder so imports like "@/store" can load.
*/

// @vitest-environment node

import { describe, expect, it } from "vitest";
import path from "path";
import viteConfig from "./vite.config";

describe("vite config", () => {
  it("maps at-imports to the frontend folder", () => {
    const config = viteConfig({ mode: "test", command: "serve", isSsrBuild: false, isPreview: false });

    expect(config.resolve?.alias).toEqual({
      "@": path.resolve(__dirname, "./"),
    });
  });
});
