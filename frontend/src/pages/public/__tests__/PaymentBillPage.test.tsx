import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { PaymentBillPage } from "../PaymentBillPage";

function renderAt(token: string) {
  return render(
    <MemoryRouter initialEntries={[`/pay/${token}`]}>
      <Routes>
        <Route path="/pay/:token" element={<PaymentBillPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("PaymentBillPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("加载成功 → 展示业主姓名与应支付金额", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        owner_name: "张三",
        owner_room: "5-203",
        payment_mode: "property_self",
        payee_name: "金桂物业",
        payee_account: "工行 6222 1234",
        payee_qr_url: null,
        payment_instructions: "到服务中心缴费",
        breakdown: {
          principal: "3000.00",
          late_fee: "200.00",
          original: "3200.00",
          waived: "0.00",
          payable: "3200.00",
          has_pending: false,
        },
      }),
    } as Response);

    renderAt("tok_ok");
    await waitFor(() => expect(screen.getByText(/张三/)).toBeDefined());
    expect(screen.getAllByText(/金桂物业/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3,?200\.00/).length).toBeGreaterThan(0);
  });

  it("链接失效（410）→ 展示失效提示", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 410,
      json: async () => ({ code: "ERR_LINK_EXPIRED", message: "缴费链接已失效" }),
    } as Response);

    renderAt("tok_expired");
    await waitFor(() =>
      expect(screen.getByText(/链接已失效|失效/)).toBeDefined(),
    );
  });

  it("网络错误 → 展示加载失败提示", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("network"));
    renderAt("tok_neterr");
    await waitFor(() => expect(screen.getByText(/加载失败/)).toBeDefined());
  });
});
