import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { openCallSocket } from "../ws-client";

// Minimal WebSocket mock that captures the onmessage handler
class FakeWebSocket {
  static instance: FakeWebSocket | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSING = 2;
  readonly CLOSED = 3;
  readyState = 1;

  constructor(_url: string) {
    FakeWebSocket.instance = this;
    // Simulate connection open asynchronously
    setTimeout(() => this.onopen?.(), 0);
  }

  send(_data: string) {}
  close() { this.onclose?.(); }

  // Helper: simulate a server message
  receive(payload: object) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

describe("ws-client risk.event routing", () => {
  beforeEach(() => {
    vi.stubGlobal("WebSocket", FakeWebSocket);
    FakeWebSocket.instance = null;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("calls onRisk when a risk.event message is received", async () => {
    const onRisk = vi.fn();

    openCallSocket({
      callId: 42,
      role: "agent",
      token: "test-token",
      baseWsUrl: "ws://localhost",
      onRisk,
    });

    // Wait for onopen to fire
    await new Promise((r) => setTimeout(r, 10));

    const riskPayload = {
      type: "risk.event",
      risk_id: "r-test-001",
      call_id: 42,
      level: "L2",
      category: "owner_threat",
      trigger: "keyword+llm",
      llm_confidence: 0.91,
      matched_keywords: ["威胁"],
      text_snippet: "我要投诉你们",
      speaker: "customer",
      ts: "2026-05-01T10:00:00Z",
    };

    FakeWebSocket.instance!.receive(riskPayload);

    expect(onRisk).toHaveBeenCalledOnce();
    const received = onRisk.mock.calls[0][0];
    expect(received.risk_id).toBe("r-test-001");
    expect(received.level).toBe("L2");
    expect(received.category).toBe("owner_threat");
    expect(received.matched_keywords).toEqual(["威胁"]);
  });

  it("does not call onRisk for non-risk.event messages", async () => {
    const onRisk = vi.fn();

    openCallSocket({
      callId: 1,
      role: "agent",
      token: "test-token",
      baseWsUrl: "ws://localhost",
      onRisk,
    });

    await new Promise((r) => setTimeout(r, 10));

    FakeWebSocket.instance!.receive({
      type: "transcript.chunk",
      text: "hello",
      speaker: "agent",
      seq: 1,
    });

    expect(onRisk).not.toHaveBeenCalled();
  });
});
