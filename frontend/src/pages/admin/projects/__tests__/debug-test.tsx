import { describe, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const { createMutate } = vi.hoisted(() => ({ createMutate: vi.fn() }));

vi.mock("@refinedev/core", () => ({
  useGo: () => vi.fn(),
  useCreate: () => ({ mutate: createMutate, mutation: { isPending: false } }),
  useList: () => ({ query: { data: { data: [] }, isLoading: false } }),
  useApiUrl: () => "http://localhost:8000/api/v1",
}));

vi.mock("../../../../components/ui/SearchableSelect", () => ({
  SearchableSelect: ({
    value,
    onChange,
    options,
    placeholder,
  }: {
    value: number | string;
    onChange: (v: string) => void;
    options: { value: number | string; label: string }[];
    placeholder?: string;
  }) => (
    <select
      value={value}
      aria-label={placeholder ?? "select"}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{placeholder ?? "— 请选择 —"}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  ),
}));

import { AdminProjectNewPage } from "../new";

describe("debug", () => {
  it("debug submit flow", () => {
    render(
      <MemoryRouter>
        <AdminProjectNewPage />
      </MemoryRouter>,
    );

    // fill name
    fireEvent.change(screen.getByPlaceholderText("例：金桂园 2026 年欠费催收"), {
      target: { value: "测试项目" },
    });

    const selects = screen.getAllByRole("combobox", { name: "— 请选择 —" });
    console.log("Number of searchable selects:", selects.length);
    
    fireEvent.change(selects[0], { target: { value: "1" } });
    fireEvent.change(selects[1], { target: { value: "2" } });
    fireEvent.change(selects[2], { target: { value: "3" } });

    // click submit
    fireEvent.click(screen.getByRole("button", { name: "创建项目" }));

    // check if error message appeared
    const errorEl = document.querySelector('[style*="color-danger"]');
    console.log("Error element:", errorEl?.textContent);
    
    // check all text on page
    const bodyText = document.body.textContent;
    if (bodyText?.includes("请")) {
      console.log("Found validation error in body");
      // find error divs
      const allText = Array.from(document.querySelectorAll('div')).filter(d => d.textContent?.includes("请")).map(d => d.textContent?.trim().substring(0, 100));
      console.log("Validation messages:", allText.filter((t): t is string => Boolean(t) && t.length < 50));
    }
    
    console.log("createMutate called:", createMutate.mock.calls.length);
  });
});
