import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const mockMutate = vi.hoisted(() => vi.fn());

vi.mock("@refinedev/core", () => ({
  useCustomMutation: () => ({
    mutate: mockMutate,
    mutation: { isPending: false },
  }),
}));

import { WorkOrderCreateModal } from "../WorkOrderCreateModal";

// 后端 WorkOrderCreate.order_type 合法枚举（schemas/work_order.py）
const VALID_TYPES = ["quality", "reduction", "dispute", "other"];

describe("WorkOrderCreateModal", () => {
  it("渲染工单类型 / 优先级 / 内容字段", () => {
    render(
      <WorkOrderCreateModal caseId={7} onClose={vi.fn()} onSuccess={vi.fn()} />,
    );
    expect(screen.getByText(/工单类型/)).toBeDefined();
    expect(screen.getByText("优先级")).toBeDefined();
    expect(screen.getByText(/工单内容/)).toBeDefined();
    expect(screen.getByRole("button", { name: "创建工单" })).toBeDefined();
  });

  it("内容为空时不提交（按钮 disabled）", () => {
    mockMutate.mockClear();
    render(
      <WorkOrderCreateModal caseId={7} onClose={vi.fn()} onSuccess={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "创建工单" }));
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("提交 payload 含合法 order_type（不再是 case_followup）", () => {
    mockMutate.mockClear();
    render(
      <WorkOrderCreateModal caseId={42} onClose={vi.fn()} onSuccess={vi.fn()} />,
    );
    fireEvent.change(screen.getByPlaceholderText(/详细描述/), {
      target: { value: "电梯故障需跟进" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建工单" }));

    expect(mockMutate).toHaveBeenCalledTimes(1);
    const arg = mockMutate.mock.calls[0][0] as {
      url: string;
      method: string;
      values: {
        case_id: number;
        order_type: string;
        priority: string;
        description: string;
      };
    };
    expect(arg.url).toBe("workorders");
    expect(arg.method).toBe("post");
    expect(arg.values.case_id).toBe(42);
    expect(VALID_TYPES).toContain(arg.values.order_type);
    expect(arg.values.order_type).not.toBe("case_followup");
    expect(arg.values.description).toBe("电梯故障需跟进");
  });

  it("切换工单类型后 payload 跟随更新", () => {
    mockMutate.mockClear();
    render(
      <WorkOrderCreateModal caseId={1} onClose={vi.fn()} onSuccess={vi.fn()} />,
    );
    // 工单类型 select 是第一个 combobox
    const typeSelect = screen.getAllByRole("combobox")[0];
    fireEvent.change(typeSelect, { target: { value: "dispute" } });
    fireEvent.change(screen.getByPlaceholderText(/详细描述/), {
      target: { value: "费用争议" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建工单" }));

    const arg = mockMutate.mock.calls[0][0] as {
      values: { order_type: string };
    };
    expect(arg.values.order_type).toBe("dispute");
  });

  it("创建成功后 onSuccess 透传工单 ID", () => {
    mockMutate.mockClear();
    mockMutate.mockImplementation(
      (
        _payload: unknown,
        opts?: { onSuccess?: (resp: { data: { id: number } }) => void },
      ) => {
        opts?.onSuccess?.({ data: { id: 99 } });
      },
    );
    const onSuccess = vi.fn();
    render(
      <WorkOrderCreateModal caseId={1} onClose={vi.fn()} onSuccess={onSuccess} />,
    );
    fireEvent.change(screen.getByPlaceholderText(/详细描述/), {
      target: { value: "xx" },
    });
    fireEvent.click(screen.getByRole("button", { name: "创建工单" }));
    expect(onSuccess).toHaveBeenCalledWith(99);
  });
});
