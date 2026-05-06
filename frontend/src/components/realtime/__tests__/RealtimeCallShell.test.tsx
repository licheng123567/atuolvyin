// frontend/src/components/realtime/__tests__/RealtimeCallShell.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { RealtimeCallShell } from "../RealtimeCallShell";
import type { RiskEvent } from "../../../lib/realtime/types";

const mockRiskL2: RiskEvent = {
  type: "risk.event",
  risk_id: "r1",
  call_id: 1,
  level: "L2",
  category: "owner_threat",
  trigger: "keyword+llm",
  llm_confidence: 0.95,
  matched_keywords: ["威胁"],
  text_snippet: "我要投诉你们",
  speaker: "customer",
  ts: "",
};

const mockRiskL1: RiskEvent = {
  type: "risk.event",
  risk_id: "r2",
  call_id: 1,
  level: "L1",
  category: "agent_minor_misconduct",
  trigger: "keyword_only",
  llm_confidence: 0.6,
  matched_keywords: [],
  text_snippet: "",
  speaker: "agent",
  ts: "",
};

vi.mock("../../../hooks/useCallSocket", () => ({
  useCallSocket: () => ({
    status: "connected",
    transcript: [
      { seq: 1, speaker: "customer", text: "您好哪位", ts: "" },
      { seq: 2, speaker: "agent", text: "您好这里是物业", ts: "" },
    ],
    suggestions: [{ id: "s1", text: "建议询问家庭收入情况" }],
    tag: null,
    risks: [mockRiskL2, mockRiskL1],
    sendFeedback: vi.fn(),
  }),
}));

describe("RealtimeCallShell", () => {
  it("renders transcript and suggestion in connected state", () => {
    render(
      <MemoryRouter>
        <RealtimeCallShell
          callId={1}
          role="agent"
          token="t"
          owner={{ name: "张三", room: "1栋101", amount_owed: "2400.00" }}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("张三")).toBeDefined();
    expect(screen.getByText("您好哪位")).toBeDefined();
    expect(screen.getByText("您好这里是物业")).toBeDefined();
    expect(screen.getByText(/建议询问家庭收入情况/)).toBeDefined();
    expect(screen.getByText(/实时/)).toBeDefined();
  });

  it("renders L2 risk banner with high-risk label and matched keywords", () => {
    render(
      <MemoryRouter>
        <RealtimeCallShell
          callId={1}
          role="agent"
          token="t"
          owner={{ name: "李四", room: "2栋202", amount_owed: "1000.00" }}
        />
      </MemoryRouter>
    );
    // L2 banner: "⛔ 高风险"
    expect(screen.getByText(/高风险/)).toBeDefined();
    // category label for owner_threat
    expect(screen.getAllByText(/业主威胁/).length).toBeGreaterThan(0);
    // matched keywords displayed in keyword line
    expect(screen.getByText(/关键词：威胁/)).toBeDefined();
    // L1 banner: "⚠ 轻微提示"
    expect(screen.getByText(/轻微提示/)).toBeDefined();
  });

  it("renders operation buttons for agent role", () => {
    render(
      <MemoryRouter>
        <RealtimeCallShell
          callId={1}
          role="agent"
          token="t"
          owner={null}
        />
      </MemoryRouter>
    );
    expect(screen.getByText("建工单")).toBeDefined();
    expect(screen.getByText("发支付码")).toBeDefined();
    expect(screen.getByText("转接督导")).toBeDefined();
  });

  it("hides operation buttons for observer role", () => {
    render(
      <MemoryRouter>
        <RealtimeCallShell
          callId={1}
          role="observer"
          token="t"
          owner={null}
        />
      </MemoryRouter>
    );
    expect(screen.queryByText("建工单")).toBeNull();
    expect(screen.getByText("正在旁听")).toBeDefined();
  });

  it("dismisses a risk banner when X is clicked", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RealtimeCallShell
          callId={1}
          role="agent"
          token="t"
          owner={null}
        />
      </MemoryRouter>
    );
    // Both banners visible initially
    expect(screen.getByText(/高风险/)).toBeDefined();
    // Click dismiss on the L2 banner (first close button)
    const closeBtns = screen.getAllByLabelText("关闭");
    await user.click(closeBtns[0]);
    // L2 banner dismissed
    expect(screen.queryByText(/高风险/)).toBeNull();
    // L1 still visible
    expect(screen.getByText(/轻微提示/)).toBeDefined();
  });
});
