import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { useState } from "react";
import { SearchableMultiSelect } from "../SearchableMultiSelect";
import type { SearchableSelectOption } from "../SearchableSelect";

const OPTIONS: SearchableSelectOption[] = [
  { value: 1, label: "张三", subtitle: "138****1234" },
  { value: 2, label: "李四", subtitle: "139****5678" },
  { value: 3, label: "王五" },
];

// 受控包装：把 onChange 反馈回 value，模拟真实使用
function Harness({
  initial = [],
  onChangeSpy,
}: {
  initial?: (string | number)[];
  onChangeSpy?: (v: (string | number)[]) => void;
}) {
  const [value, setValue] = useState<(string | number)[]>(initial);
  return (
    <SearchableMultiSelect
      value={value}
      options={OPTIONS}
      placeholder="请选择人员"
      onChange={(v) => {
        setValue(v);
        onChangeSpy?.(v);
      }}
    />
  );
}

// 下拉框（含搜索框 + 选项列表）—— 用于把选项点击与触发器里的 chip 区分开
function openDropdown(): HTMLElement {
  fireEvent.click(screen.getByRole("button"));
  const searchInput = screen.getByPlaceholderText("搜索...");
  const dropdown = searchInput.closest("div")?.parentElement;
  if (!dropdown) throw new Error("下拉框未找到");
  return dropdown;
}

describe("SearchableMultiSelect", () => {
  it("无选中时显示 placeholder", () => {
    render(<Harness />);
    expect(screen.getByText("请选择人员")).toBeDefined();
  });

  it("已选项以 chip 呈现", () => {
    render(<Harness initial={[1, 2]} />);
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("李四")).toBeDefined();
  });

  it("点击触发器展开下拉，列出全部选项", () => {
    render(<Harness />);
    const dropdown = openDropdown();
    expect(within(dropdown).getByText("张三")).toBeDefined();
    expect(within(dropdown).getByText("王五")).toBeDefined();
  });

  it("搜索框过滤选项", () => {
    render(<Harness />);
    const dropdown = openDropdown();
    fireEvent.change(screen.getByPlaceholderText("搜索..."), {
      target: { value: "李" },
    });
    expect(within(dropdown).getByText("李四")).toBeDefined();
    expect(within(dropdown).queryByText("王五")).toBeNull();
  });

  it("点击选项可多选 / 取消选", () => {
    const spy = vi.fn();
    render(<Harness onChangeSpy={spy} />);
    const dropdown = openDropdown();
    // 选「张三」
    fireEvent.click(within(dropdown).getByText("张三"));
    expect(spy).toHaveBeenLastCalledWith([1]);
    // 再选「王五」—— 下拉保持打开，可连续多选
    fireEvent.click(within(dropdown).getByText("王五"));
    expect(spy).toHaveBeenLastCalledWith([1, 3]);
    // 再点「张三」取消选
    fireEvent.click(within(dropdown).getByText("张三"));
    expect(spy).toHaveBeenLastCalledWith([3]);
  });

  it("点击 chip 上的 X 移除该项", () => {
    const spy = vi.fn();
    render(<Harness initial={[1, 2]} onChangeSpy={spy} />);
    // chip「张三」内的 X：定位 chip 容器后取其 svg
    const chip = screen.getByText("张三").closest("span");
    const xIcon = chip?.querySelector("svg");
    expect(xIcon).not.toBeNull();
    fireEvent.click(xIcon as SVGElement);
    expect(spy).toHaveBeenLastCalledWith([2]);
  });
});
