import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// vi.hoisted ensures the mock factory runs before module imports
const mockMutate = vi.hoisted(() => vi.fn());

vi.mock("@refinedev/core", () => ({
  useCustom: vi.fn(),
  useCustomMutation: vi.fn(),
  useList: vi.fn(),
}));

import { useCustom, useCustomMutation, useList } from "@refinedev/core";
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
    mutate: mockMutate,
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

  it("提交换算：填 8 点保存，mutate 入参 provider_agent_commission_rate === 0.08", () => {
    mockMutate.mockReset();
    setupMocks();
    render(
      <MemoryRouter>
        <ProviderProjectsPage />
      </MemoryRouter>,
    );
    // open modal for first project (翠竹苑, rate=null — but any project works)
    const buttons = screen.getAllByText(/设置佣金率/);
    fireEvent.click(buttons[0]);

    // fill in percentage input
    const input = screen.getByRole("spinbutton");
    fireEvent.change(input, { target: { value: "8" } });

    // click save
    fireEvent.click(screen.getByText("保存"));

    expect(mockMutate).toHaveBeenCalledTimes(1);
    const callArgs = mockMutate.mock.calls[0][0] as {
      values: { provider_agent_commission_rate: number };
    };
    expect(callArgs.values.provider_agent_commission_rate).toBeCloseTo(0.08, 10);
  });

  it("onError 展示：mutate 触发 onError 时，错误 message 显示在弹窗内", () => {
    mockMutate.mockReset();
    mockMutate.mockImplementation(
      (
        _payload: unknown,
        options?: { onError?: (e: unknown) => void },
      ) => {
        options?.onError?.({
          response: { data: { message: "项目不存在或不属本服务商" } },
        });
      },
    );
    setupMocks();
    render(
      <MemoryRouter>
        <ProviderProjectsPage />
      </MemoryRouter>,
    );
    const buttons = screen.getAllByText(/设置佣金率/);
    fireEvent.click(buttons[0]);

    const input = screen.getByRole("spinbutton");
    fireEvent.change(input, { target: { value: "8" } });
    fireEvent.click(screen.getByText("保存"));

    expect(screen.getByText("项目不存在或不属本服务商")).toBeDefined();
  });
});
