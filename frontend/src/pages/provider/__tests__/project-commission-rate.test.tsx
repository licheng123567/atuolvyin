import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { useCustom, useCustomMutation, useList } from "@refinedev/core";

vi.mock("@refinedev/core", () => ({
  useCustom: vi.fn(),
  useCustomMutation: vi.fn(),
  useList: vi.fn(),
}));

import { ProviderProjectsPage } from "../../provider/projects/index";

const mockItems = [
  {
    project_id: 1,
    project_name: "阳光花园",
    tenant_name: "金桂物业",
    plan_start: null,
    plan_end: null,
    provider_pm_user_id: null,
    provider_pm_name: null,
    provider_agent_commission_rate: "0.1000",
  },
  {
    project_id: 2,
    project_name: "翠竹苑",
    tenant_name: "绿城物业",
    plan_start: null,
    plan_end: null,
    provider_pm_user_id: null,
    provider_pm_name: null,
    provider_agent_commission_rate: null,
  },
];

function setupMocks() {
  vi.mocked(useCustom).mockReturnValue({
    query: {
      data: { data: { items: mockItems } },
      isLoading: false,
      refetch: vi.fn(),
    },
  } as ReturnType<typeof useCustom>);

  vi.mocked(useCustomMutation).mockReturnValue({
    mutate: vi.fn(),
    mutation: { isPending: false },
  } as unknown as ReturnType<typeof useCustomMutation>);

  vi.mocked(useList).mockReturnValue({
    query: { data: { data: [] } },
  } as unknown as ReturnType<typeof useList>);
}

describe("服务商项目 — D2 佣金率列", () => {
  it("renders the commission rate column header", () => {
    setupMocks();
    render(
      <MemoryRouter>
        <ProviderProjectsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/服务商佣金率/)).toBeDefined();
  });

  it("renders formatted commission rate for project with rate", () => {
    setupMocks();
    render(
      <MemoryRouter>
        <ProviderProjectsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("10.0%")).toBeDefined();
  });

  it("renders default text for project without rate", () => {
    setupMocks();
    render(
      <MemoryRouter>
        <ProviderProjectsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/继承默认/)).toBeDefined();
  });

  it("renders 设置佣金率 button for each row", () => {
    setupMocks();
    render(
      <MemoryRouter>
        <ProviderProjectsPage />
      </MemoryRouter>,
    );
    const buttons = screen.getAllByText(/设置佣金率/);
    expect(buttons.length).toBe(2);
  });

  it("opens CommissionRateModal when 设置佣金率 button is clicked", () => {
    setupMocks();
    render(
      <MemoryRouter>
        <ProviderProjectsPage />
      </MemoryRouter>,
    );
    const buttons = screen.getAllByText(/设置佣金率/);
    fireEvent.click(buttons[0]);
    expect(screen.getByText(/设置服务商佣金率/)).toBeDefined();
  });
});
