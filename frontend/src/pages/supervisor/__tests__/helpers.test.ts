// frontend/src/pages/supervisor/__tests__/helpers.test.ts
import { describe, it, expect } from "vitest";
import { getLabelStatus } from "../helpers";

describe("getLabelStatus", () => {
  it("returns unlabeled when no supervisor_label", () => {
    expect(getLabelStatus(null)).toBe("unlabeled");
  });
  it("returns good", () => {
    expect(getLabelStatus("good")).toBe("good");
  });
  it("returns bad", () => {
    expect(getLabelStatus("bad")).toBe("bad");
  });
});
