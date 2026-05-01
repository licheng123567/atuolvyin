// frontend/src/components/realtime/RealtimeCallShell.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCallSocket } from "../../hooks/useCallSocket";
import { postSuggestionFeedback } from "../../lib/realtime/feedback-api";
import { ConnectionBadge } from "./ConnectionBadge";
import { TranscriptStream } from "./TranscriptStream";
import { SuggestionCardStack } from "./SuggestionCardStack";

interface OwnerSummary {
  name: string;
  building?: string;
  room?: string;
  amount_owed?: string;
}

interface Props {
  callId: number;
  role: "agent" | "observer";
  token: string;
  owner: OwnerSummary | null;
}

export function RealtimeCallShell({ callId, role, token, owner }: Props) {
  const navigate = useNavigate();
  const { status, transcript, suggestions, tag, sendFeedback } = useCallSocket({ callId, role, token });
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (tag !== null) {
      // Server confirmed final analysis — jump to call detail
      const timeout = setTimeout(() => navigate(`/calls/${callId}`), 800);
      return () => clearTimeout(timeout);
    }
  }, [tag, callId, navigate]);

  const handleFeedback = (id: string, action: "adopt" | "ignore") => {
    sendFeedback(id, action);  // WS ack for instant UX
    void postSuggestionFeedback(callId, id, action, token);  // durable
  };

  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <header className="flex items-center justify-between rounded-lg bg-white px-4 py-2 shadow-sm">
        <div className="font-mono text-lg text-slate-700">通话 {mm}:{ss}</div>
        <ConnectionBadge status={status} />
        {role === "observer" && (
          <span className="text-sm text-slate-500">正在旁听</span>
        )}
      </header>

      <div className="grid flex-1 gap-4" style={{ gridTemplateColumns: "280px 1fr 320px" }}>
        <aside className="rounded-lg bg-white p-4 shadow-sm">
          {owner ? (
            <>
              <div className="text-xl font-semibold">{owner.name}</div>
              <div className="mt-1 text-sm text-slate-500">
                {owner.building} {owner.room}
              </div>
              {owner.amount_owed && (
                <div className="mt-3 text-base text-rose-600">
                  欠费 ¥{owner.amount_owed}
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-slate-400">加载业主信息中…</div>
          )}
        </aside>

        <TranscriptStream chunks={transcript} />

        <aside>
          <SuggestionCardStack
            suggestions={suggestions}
            onFeedback={handleFeedback}
            readOnly={role === "observer"}
          />
        </aside>
      </div>
    </div>
  );
}
