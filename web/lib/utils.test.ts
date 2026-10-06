import { describe, expect, it } from "vitest";

import { cn } from "@/lib/utils";

describe("cn", () => {
  it("fusionne les classes et garde la dernière en cas de conflit Tailwind", () => {
    expect(cn("px-2 py-1", "px-4")).toBe("py-1 px-4");
  });

  it("ignore les valeurs vides", () => {
    expect(cn("text-sm", false, undefined, "font-medium")).toBe("text-sm font-medium");
  });
});
