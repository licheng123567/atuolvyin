import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PaymentLinkQrModal } from "../PaymentLinkQrModal";

const BREAKDOWN = {
  principal: "3000.00",
  late_fee: "200.00",
  original: "3200.00",
  waived: "200.00",
  payable: "3000.00",
  has_pending: false,
};

const PROPS = {
  token: "tok_abc123",
  breakdown: BREAKDOWN,
  sentTo: "138****1234",
  onClose: vi.fn(),
};

describe("PaymentLinkQrModal", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("展示支付明细：应缴 / 已减免 / 应支付", () => {
    render(<PaymentLinkQrModal {...PROPS} />);
    expect(screen.getByText(/应缴合计/)).toBeDefined();
    expect(screen.getByText(/已减免/)).toBeDefined();
    expect(screen.getByText(/应支付/)).toBeDefined();
    expect(screen.getAllByText(/3,?000\.00/).length).toBeGreaterThan(0);
  });

  it("渲染缴费二维码（size=180 的 svg）", () => {
    const { container } = render(<PaymentLinkQrModal {...PROPS} />);
    expect(container.querySelector('svg[width="180"]')).not.toBeNull();
  });

  it("has_pending 为真时显示待审批减免提醒", () => {
    render(
      <PaymentLinkQrModal
        {...PROPS}
        breakdown={{ ...BREAKDOWN, has_pending: true }}
      />,
    );
    expect(screen.getByText(/待审批减免/)).toBeDefined();
  });

  it("has_pending 为假时不显示提醒", () => {
    render(<PaymentLinkQrModal {...PROPS} />);
    expect(screen.queryByText(/待审批减免/)).toBeNull();
  });

  it("点击复制按钮 → 缴费链接写入剪贴板", () => {
    render(<PaymentLinkQrModal {...PROPS} />);
    fireEvent.click(screen.getByText("复制链接"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining("/pay/tok_abc123"),
    );
  });

  it("点击完成触发 onClose", () => {
    const onClose = vi.fn();
    render(<PaymentLinkQrModal {...PROPS} onClose={onClose} />);
    fireEvent.click(screen.getByText("完成"));
    expect(onClose).toHaveBeenCalled();
  });

  it("waived 为 0 时不显示已减免行", () => {
    render(
      <PaymentLinkQrModal
        {...PROPS}
        breakdown={{ ...BREAKDOWN, waived: "0.00" }}
      />,
    );
    expect(screen.queryByText(/已减免/)).toBeNull();
  });
});
