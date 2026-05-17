import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api", () => ({
  useProviderLegalCases: vi.fn(),
}));
vi.mock("@refinedev/core", () => ({ useGo: () => vi.fn() }));

import { useProviderLegalCases } from "../api";
import { ProviderLegalCasesPage } from "../cases/index";

describe("ProviderLegalCasesPage", () => {
  it("renders case row with owner and project", () => {
    vi.mocked(useProviderLegalCases).mockReturnValue({
      items: [
        {
          case_id: 1, owner_name: "张三", owner_phone_masked: "138****8888",
          building: "1栋", room: "101", project_id: 9, project_name: "阳光花园",
          amount_owed: "3000.00", months_overdue: 3, stage: "跟进中",
        },
      ],
      total: 1, isLoading: false, isError: false,
    });
    render(<MemoryRouter><ProviderLegalCasesPage /></MemoryRouter>);
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("阳光花园")).toBeDefined();
    expect(screen.getByText("138****8888")).toBeDefined();
  });

  it("shows loading indicator when isLoading is true", () => {
    vi.mocked(useProviderLegalCases).mockReturnValue({
      items: [], total: 0, isLoading: true, isError: false,
    });
    render(<MemoryRouter><ProviderLegalCasesPage /></MemoryRouter>);
    expect(screen.getByText("加载中…")).toBeDefined();
  });

  it("shows empty state message when no cases exist", () => {
    vi.mocked(useProviderLegalCases).mockReturnValue({
      items: [], total: 0, isLoading: false, isError: false,
    });
    render(<MemoryRouter><ProviderLegalCasesPage /></MemoryRouter>);
    expect(screen.getByText("暂无案件")).toBeDefined();
  });
});
