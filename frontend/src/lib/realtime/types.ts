// frontend/src/lib/realtime/types.ts

export interface TranscriptChunk {
  seq: number;
  speaker: "agent" | "customer" | string;
  text: string;
  ts: string;  // ISO timestamp
  utterance_end?: boolean;
}

export interface Suggestion {
  id: string;
  text: string;
  intent?: string;
  confidence?: number;
}

export interface TagPayload {
  intent?: string;
  promise_date?: string;
  promise_amount?: number;
  summary?: string;
}

export type CallSocketStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "failed"
  | "call_ended";

export interface RiskEvent {
  type: "risk.event";
  risk_id: string;
  call_id: number;
  level: "L1" | "L2";
  category: "owner_abuse" | "owner_threat" | "agent_violation" | "agent_minor_misconduct";
  trigger: "keyword_only" | "llm_only" | "keyword+llm";
  llm_confidence: number;
  matched_keywords: string[];
  text_snippet: string;
  speaker: "agent" | "customer";
  ts: string;
}

export interface CallSocketOptions {
  callId: number;
  role: "agent" | "observer";
  token: string;
  baseWsUrl?: string;  // default derived from window.location
  onTranscript?: (chunk: TranscriptChunk) => void;
  onSuggestion?: (s: Suggestion) => void;
  onTagReady?: (tag: TagPayload) => void;
  onStatusChange?: (status: CallSocketStatus) => void;
  onRisk?: (event: RiskEvent) => void;
}

export interface CallSocketHandle {
  close: () => void;
  sendFeedback: (suggestionId: string, action: "adopt" | "ignore") => void;
}
