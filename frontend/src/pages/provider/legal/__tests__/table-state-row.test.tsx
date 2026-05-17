import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { TableStateRow } from "../TableStateRow";

describe("TableStateRow", () => {
  it("renders children inside a td with the given colSpan", () => {
    const { container } = render(
      <table>
        <tbody>
          <TableStateRow colSpan={6}>加载中…</TableStateRow>
        </tbody>
      </table>,
    );
    const td = container.querySelector("td");
    expect(td).not.toBeNull();
    expect(td?.getAttribute("colspan")).toBe("6");
    expect(td?.textContent).toBe("加载中…");
  });
});
