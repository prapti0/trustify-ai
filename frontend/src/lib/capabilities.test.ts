import { describe, expect, it } from "vitest";
import { countEngines } from "./capabilities";

describe("countEngines", () => {
  it("counts ready and not-integrated engines without inventing a third bucket", () => {
    const counts = countEngines([
      { status: "ready" },
      { status: "not_integrated" },
      { status: "not_integrated" },
    ]);
    expect(counts).toEqual({ ready: 1, notIntegrated: 2 });
  });
});
