import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PaymentLinkQrModal } from "../PaymentLinkQrModal";

const PROPS = {
  link: "https://pay.autoluyin.example.com/h5/abc123token",
  shortLink: "https://yzhc.cn/p/abc123",
  sentTo: "138****1234",
  onClose: vi.fn(),
};

describe("PaymentLinkQrModal", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("展示业主掩码手机号", () => {
    render(<PaymentLinkQrModal {...PROPS} />);
    expect(screen.getByText(/138\*\*\*\*1234/)).toBeDefined();
  });

  it("展示可复制短链", () => {
    render(<PaymentLinkQrModal {...PROPS} />);
    expect(screen.getByText("https://yzhc.cn/p/abc123")).toBeDefined();
  });

  it("渲染缴费链接二维码（size=180 的 svg）", () => {
    const { container } = render(<PaymentLinkQrModal {...PROPS} />);
    // QRCodeSVG size=180 → <svg width="180">；lucide 图标 svg 尺寸不为 180
    expect(container.querySelector('svg[width="180"]')).not.toBeNull();
  });

  it("点击复制按钮 → 短链写入剪贴板", () => {
    render(<PaymentLinkQrModal {...PROPS} />);
    fireEvent.click(screen.getByText("复制链接"));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "https://yzhc.cn/p/abc123",
    );
  });

  it("点击完成触发 onClose", () => {
    const onClose = vi.fn();
    render(<PaymentLinkQrModal {...PROPS} onClose={onClose} />);
    fireEvent.click(screen.getByText("完成"));
    expect(onClose).toHaveBeenCalled();
  });
});
