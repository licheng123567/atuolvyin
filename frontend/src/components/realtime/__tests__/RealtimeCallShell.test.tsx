// frontend/src/components/realtime/__tests__/RealtimeCallShell.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RealtimeCallShell } from "../RealtimeCallShell";

vi.mock("../../../hooks/useCallSocket", () => ({
  useCallSocket: () => ({
    status: "connected",
    transcript: [
      { seq: 1, speaker: "customer", text: "您好哪位", ts: "" },
      { seq: 2, speaker: "agent", text: "您好这里是物业", ts: "" },
    ],
    suggestions: [{ id: "s1", text: "建议询问家庭收入情况" }],
    tag: null,
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
});
