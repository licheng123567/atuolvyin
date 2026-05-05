import { useEffect, useRef, useState } from "react";
import { openCallSocket } from "../lib/realtime/ws-client";
import type {
  CallSocketHandle,
  CallSocketStatus,
  RiskEvent,
  Suggestion,
  TagPayload,
  TranscriptChunk,
} from "../lib/realtime/types";

export interface UseCallSocketArgs {
  callId: number;
  role: "agent" | "observer";
  token: string;
}

export interface UseCallSocketResult {
  status: CallSocketStatus;
  transcript: TranscriptChunk[];
  suggestions: Suggestion[];
  tag: TagPayload | null;
  risks: RiskEvent[];
  sendFeedback: (id: string, action: "adopt" | "ignore") => void;
}

export function useCallSocket(args: UseCallSocketArgs): UseCallSocketResult {
  const [status, setStatus] = useState<CallSocketStatus>("connecting");
  const [transcript, setTranscript] = useState<TranscriptChunk[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [tag, setTag] = useState<TagPayload | null>(null);
  const [risks, setRisks] = useState<RiskEvent[]>([]);
  const handleRef = useRef<CallSocketHandle | null>(null);

  useEffect(() => {
    const handle = openCallSocket({
      callId: args.callId,
      role: args.role,
      token: args.token,
      onStatusChange: setStatus,
      onTranscript: (c) => setTranscript((prev) => [...prev, c]),
      onSuggestion: (s) => setSuggestions((prev) => [...prev, s]),
      onTagReady: (t) => setTag(t),
      onRisk: (e) =>
        setRisks((prev) => {
          if (prev.some((r) => r.risk_id === e.risk_id)) return prev;
          return [...prev, e];
        }),
    });
    handleRef.current = handle;
    return () => handle.close();
  }, [args.callId, args.role, args.token]);

  return {
    status,
    transcript,
    suggestions,
    tag,
    risks,
    sendFeedback: (id, action) => handleRef.current?.sendFeedback(id, action),
  };
}
