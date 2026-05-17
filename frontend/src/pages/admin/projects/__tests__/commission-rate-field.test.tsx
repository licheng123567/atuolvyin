import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@refinedev/core", () => ({
  useGo: () => vi.fn(),
  useCreate: () => ({ mutate: vi.fn(), mutation: { isPending: false } }),
  useList: () => ({ query: { data: { data: [] }, isLoading: false } }),
  useApiUrl: () => "http://localhost:8000/api/v1",
}));

// SearchableSelect relies on no external deps — mock it for simplicity
vi.mock("../../../../components/ui/SearchableSelect", () => ({
  SearchableSelect: () => null,
}));

import { AdminProjectNewPage } from "../new";

describe("项目创建表单 — D1 内勤佣金率", () => {
  it("renders the internal-agent commission rate field", () => {
    render(
      <MemoryRouter>
        <AdminProjectNewPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/内勤催收员佣金率/)).toBeDefined();
  });
});
