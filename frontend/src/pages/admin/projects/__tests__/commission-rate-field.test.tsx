import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// vi.hoisted — 在模块求值之前定义，工厂函数和测试体均可引用
const { createMutate } = vi.hoisted(() => ({ createMutate: vi.fn() }));

vi.mock("@refinedev/core", () => ({
  useGo: () => vi.fn(),
  useCreate: () => ({ mutate: createMutate, mutation: { isPending: false } }),
  useList: () => ({ query: { data: { data: [] }, isLoading: false } }),
  useApiUrl: () => "http://localhost:8000/api/v1",
}));

// SearchableSelect mock 成真实的 <select>。
// 加入固定的 dummy options（value "1"/"2"/"3"），使 fireEvent.change 能让 jsdom select
// 找到匹配 option，React controlled value 才能正确更新。
// useList 返回 [] 时 options prop 为空，若不加 dummy options，
// fireEvent.change 虽触发 onChange 但 e.target.value 仍为 ""，state 不会变。
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
      {/* dummy options 用于测试时 fireEvent.change 能命中有效 option */}
      <option value="1">dummy-1</option>
      <option value="2">dummy-2</option>
      <option value="3">dummy-3</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  ),
}));

import { AdminProjectNewPage } from "../new";

/**
 * 填写所有必填字段（name / propertyPmId / coordinatorId / legalId）。
 * SearchableSelect 按 DOM 出现顺序：0=物业项目负责人, 1=物业协调员, 2=法务对接人。
 */
function fillRequiredFields() {
  fireEvent.change(screen.getByPlaceholderText("例：金桂园 2026 年欠费催收"), {
    target: { value: "测试项目" },
  });

  const searchableSelects = screen.getAllByRole("combobox", { name: "— 请选择 —" });
  fireEvent.change(searchableSelects[0], { target: { value: "1" } }); // propertyPmId
  fireEvent.change(searchableSelects[1], { target: { value: "2" } }); // coordinatorId
  fireEvent.change(searchableSelects[2], { target: { value: "3" } }); // legalId
}

describe("项目创建表单 — D1 内勤佣金率", () => {
  it("renders the internal-agent commission rate field", () => {
    render(
      <MemoryRouter>
        <AdminProjectNewPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/内勤催收员佣金率/)).toBeDefined();
  });

  it("填 5 提交 → internal_agent_commission_rate 换算为 0.05", () => {
    createMutate.mockClear();
    render(
      <MemoryRouter>
        <AdminProjectNewPage />
      </MemoryRouter>,
    );

    fillRequiredFields();

    // 填写内勤佣金率 5（百分比），提交后应换算为 0.05
    fireEvent.change(screen.getByPlaceholderText("例：5"), {
      target: { value: "5" },
    });

    fireEvent.click(screen.getByRole("button", { name: "创建项目" }));

    expect(createMutate).toHaveBeenCalled();
    const callArg = createMutate.mock.calls[0][0] as {
      values: { internal_agent_commission_rate: number };
    };
    expect(callArg.values.internal_agent_commission_rate).toBe(0.05);
  });

  it("内勤佣金率留空 → 提交值为 null", () => {
    createMutate.mockClear();
    render(
      <MemoryRouter>
        <AdminProjectNewPage />
      </MemoryRouter>,
    );

    fillRequiredFields();

    // 不填内勤佣金率（保持默认空字符串）
    fireEvent.click(screen.getByRole("button", { name: "创建项目" }));

    expect(createMutate).toHaveBeenCalled();
    const callArg = createMutate.mock.calls[0][0] as {
      values: { internal_agent_commission_rate: null };
    };
    expect(callArg.values.internal_agent_commission_rate).toBeNull();
  });
});
