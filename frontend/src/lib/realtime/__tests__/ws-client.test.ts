// frontend/src/lib/realtime/__tests__/ws-client.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { openCallSocket } from "../ws-client";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  readyState = 0;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
    this.onclose?.(new CloseEvent("close"));
  }
  fakeOpen() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }
  fakeMessage(payload: unknown) {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(payload) }));
  }
  fakeFailure() {
    this.onerror?.(new Event("error"));
    this.close();
  }
}

describe("openCallSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    // @ts-expect-error — override global for the test
    global.WebSocket = MockWebSocket;
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("dispatches transcript / suggestion / tag events", () => {
    const transcripts: unknown[] = [];
    const suggestions: unknown[] = [];
    const tags: unknown[] = [];
    const statuses: string[] = [];

    openCallSocket({
      callId: 42,
      role: "agent",
      token: "t",
      baseWsUrl: "ws://test",
      onTranscript: (c) => transcripts.push(c),
      onSuggestion: (s) => suggestions.push(s),
      onTagReady: (t) => tags.push(t),
      onStatusChange: (s) => statuses.push(s),
    });

    const sock = MockWebSocket.instances[0];
    sock.fakeOpen();
    sock.fakeMessage({ type: "transcript.chunk", seq: 1, speaker: "customer", text: "hi", ts: "" });
    sock.fakeMessage({ type: "suggestion.ready", id: "s1", text: "say x" });
    sock.fakeMessage({ type: "tag.ready", intent: "promise_pay" });

    expect(transcripts).toHaveLength(1);
    expect(suggestions).toHaveLength(1);
    expect(tags).toHaveLength(1);
    expect(statuses).toContain("connected");
  });

  it("attempts exponential backoff reconnects", () => {
    openCallSocket({ callId: 1, role: "agent", token: "t", baseWsUrl: "ws://test" });

    // Force the initial socket into a failed state
    MockWebSocket.instances[0].fakeFailure();
    expect(MockWebSocket.instances).toHaveLength(1);

    vi.advanceTimersByTime(1100);  // 1s backoff
    expect(MockWebSocket.instances).toHaveLength(2);

    MockWebSocket.instances[1].fakeFailure();
    vi.advanceTimersByTime(2100);  // 2s backoff
    expect(MockWebSocket.instances).toHaveLength(3);
  });

  it("sends ping on heartbeat interval", () => {
    openCallSocket({ callId: 1, role: "agent", token: "t", baseWsUrl: "ws://test" });
    const sock = MockWebSocket.instances[0];
    sock.fakeOpen();
    vi.advanceTimersByTime(30_000);
    expect(sock.sent.some((s) => s.includes('"ping"'))).toBe(true);
  });

  it("sendFeedback writes a JSON envelope", () => {
    const handle = openCallSocket({ callId: 1, role: "agent", token: "t", baseWsUrl: "ws://test" });
    const sock = MockWebSocket.instances[0];
    sock.fakeOpen();
    handle.sendFeedback("sug-1", "adopt");
    const last = sock.sent[sock.sent.length - 1];
    const parsed = JSON.parse(last);
    expect(parsed).toMatchObject({ type: "suggestion.feedback", id: "sug-1", action: "adopt" });
  });
});
